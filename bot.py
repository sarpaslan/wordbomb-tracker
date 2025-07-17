import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, Select
import logging
from dotenv import load_dotenv
import os
import aiosqlite
import random
import datetime
import time
from datetime import datetime, timedelta
import motor.motor_asyncio

# Load token
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# --- New Constants ---
# Ask Hector for this connection string and put it in your .env file
MONGO_URI = os.getenv('MONGO_URI')
# ID of the private channel where suggestions will be sent for approval
APPROVAL_CHANNEL_ID = 1395207582985097276 # <--- ⚠️ CHANGE THIS TO YOUR LM'S PRIVATE CHANNEL ID

# --- MongoDB Setup ---
client = None
db = None
questions_collection = None

# Logging setup
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents, log_handler=handler, log_level=logging.DEBUG, help_command=None)

# Threshold-based roles
MESSAGE_THRESHOLDS = {
    100: "Active",
    1000: "Talker",
    5000: "Speaker",
    10000: "Veteran",
    20000: "Elite",
    40000: "Legend"
}

LANGUAGE_MOD_IDS = {
    265196052192165888,  # Hector (en-US, ru), admin, legend
    1032529324303200278,  # Lex-ico (es-ES, mc-MC, ca-CA), admin, legend
    510424968408989706,  # jarks (id-ID, en-US), admin, legend
    735018514930335746,  # arcy (de-DE), admin
    841195211929813022,  # Blackstone (de-DE), admin
    699006597732630529,  # Häschen (de-DE), admin, legend
    726034544142188645,  # zyth (en-US), admin, legend
    751164716692406503,  # cattos (pt-BR), admin
    982489812768555088,  # rynamarole (en-US), admin, legend
    1293924095519490070,  # piwb (fr-FR), admin, legend
    871395810871504978,  # revere1991 (fr-FR), admin
    1201722285149671437,  # Rezeze (fr-FR), admin
    988590038105329726,  # Luftspejling (fr-FR), admin
    766147685035933737,  # vanity (mc-MC), admin
    821185023058247680,  # niko (it-IT, en-US, nl), admin (some legend false)
    604038789048041486,  # Anders8K (sv-SE), admin
    534916027931164673,  # myllerrys (fr-FR), admin
    872808479260303400,  # raul (es-ES), admin, legend
    892125668459036742,  # Joe mama (en-US), admin, legend
    745927362427879464,  # SplashMaster (ru), admin, legend false
    448419862767730703,  # kisaragi (tl-TL), admin, legend false
    918908049194889236,  # ayberk (tr-TR), admin, legend false
    945440695924162690,  # finesse (ru), admin, legend false
    #849827666064048178, #test
}

LANGUAGE_CHANNEL_IDS = {
    1310645572373450782,  # en-US suggest words channel
    1331697536599064626,  # fr-FR suggest words channel
    1334948522436591717,  # tr-TR suggest words channel
    1335339488762920991,  # es-ES suggest words channel
    1341035170588917760,  # id-ID suggest words channel
    1342836273819418737,  # pt-BR suggest words channel
    1333229725761540137,  # de-DE suggest words channel
    1348116185278844979,  # tl-TL suggest words channel
    1356433831498088502,  # mc-MC suggest words channel
    1359967225410486352,  # it-IT suggest words channel
    1367131592505557012,  # sv-SE suggest words channel
    1371921886245818418,  # ru suggest words channel
    1390240204459085844,  # nl suggest words channel
    #1392345870384762961, # test
}

EXCLUDED_CHANNEL_IDS = {
    1332163511010332773,  # en-US search words channel
    1332410833204023399,  # fr-FR search words channel
    1335029016637472849,  # tr-TR search words channel
    1335339297695465553,  # es-ES search words channel
    1341035044067737681,  # id-ID search words channel
    1342836151475503114,  # pt-BR search words channel
    1344510594191200286,  # de-DE search words channel
    1348116146150445057,  # tl-TL search words channel
    1356435274946711623,  # mc-MC search words channel
    1359967242040774888,  # it-IT search words channel
    1367131564642795581,  # sv-SE search words channel
    1371885469373042750,  # ru search words channel
    1383399906378518558,  # nl search words channel
    1383399537661444146,  # finnish search words channel
    1392393127700205680, # music commands channel
    1328176869572612288, # normal commands channel
    1349650156001431592, # what channel
}
voice_states = {}

EXCLUDED_VC_IDS = {1390402088483422289, 1390454038142914720}

last_message_times = {}

OTHER_BOTS_COMMANDS = {
    "Word Bomb": ["/claims - Get claims information",
                  "/collection - Get collection information for a user",
                  "/discoveries - Get discovery information for a user",
                  "/inventory - See your word and syllable inventory",
                  "/love - See how much love sparks between two users!",
                  "/profile - Get profile information for a user",
                  "/wallet - See your wallet!",
                  "/word - Get information about a word",
                  "/wordle - Get Wordle results for a user",
                  "!i - Get information about a word",
                  "!s - Get information about a syllable"],
    "Word Bomb Tracker": ["!leaderboards - Get information on the leaderboard",
                          "!help - Get help on the usage of commands"],
    "Talk to get more roles!": ["Active - 100 messages",
                                "Talker - 1,000 messages",
                                "Speaker - 5,000 messages",
                                "Veteran - 10,000 messages",
                                "Elite - 20,000 messages",
                                "Legend - 40,000 messages"]
}

POINT_LOGS_CHANNEL = None

@bot.event
async def on_ready():
    # Make the variables accessible globally
    global client, db, questions_collection

    # --- NEW: Initialize MongoDB client inside the running loop ---
    print("[INFO] Initializing MongoDB connection...")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        db = client.questions
        questions_collection = db.questions
        # The ismaster command is a lightweight way to force the
        # client to connect and confirm the connection is active.
        await client.admin.command('ismaster')
        print("[SUCCESS] MongoDB connection established.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        # You might want to shut down the bot if the DB connection fails
        # await bot.close()
        return

    global POINT_LOGS_CHANNEL
    POINT_LOGS_CHANNEL = bot.get_channel(1392585590532341782)

    if POINT_LOGS_CHANNEL:
        print(f"[DEBUG] POINT_LOGS_CHANNEL loaded: {POINT_LOGS_CHANNEL.name} ({POINT_LOGS_CHANNEL.id})")
    else:
        print("[ERROR] POINT_LOGS_CHANNEL could not be loaded.")

    for cmd in bot.commands:
        print(f"Loaded command: {cmd.name}")
    print(f"[DEBUG] Bot is ready. Logged in as {bot.user} ({bot.user.id})")
    async with aiosqlite.connect("server_data.db") as db:
        # No changes needed to the first set of tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.execute("CREATE TABLE IF NOT EXISTS bug_points (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db.execute("CREATE TABLE IF NOT EXISTS idea_points (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db.execute("CREATE TABLE IF NOT EXISTS suggest_points (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db.execute("CREATE TABLE IF NOT EXISTS voice_time (user_id INTEGER PRIMARY KEY, seconds INTEGER NOT NULL)")
        await db.execute("CREATE TABLE IF NOT EXISTS bug_pointed_messages (message_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS idea_pointed_messages (message_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS suggest_pointed_messages (message_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS candies (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")

        # ✅ CHANGE: Modified message_history to store data weekly
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_history (
                user_id INTEGER,
                week TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, week)
            )
        """)

        # ✅ NEW: Create the table for storing weekly leaderboard snapshots
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_leaderboard_snapshot (
                week TEXT,
                user_id INTEGER,
                rank INTEGER,
                total_messages INTEGER,
                PRIMARY KEY (week, user_id)
            )
        """)

        # --- NEW: Table for tracking active voice sessions ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_voice_sessions (
                user_id INTEGER PRIMARY KEY,
                join_time_iso TEXT NOT NULL
            )
        """)

        await db.commit()

    # --- NEW: Reconcile voice states on startup ---
    print("[INFO] Reconciling voice states on startup...")
    startup_time = datetime.utcnow()
    
    # Get all users who are actually in a VC right now
    current_vc_users = set()
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.id not in EXCLUDED_VC_IDS:
                for member in channel.members:
                    if not member.bot:
                        current_vc_users.add(member.id)
    
    # Get all users the DB thinks are in a VC
    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute("SELECT user_id, join_time_iso FROM active_voice_sessions")
        db_sessions = await cursor.fetchall()

        for user_id, join_time_iso in db_sessions:
            join_time = datetime.fromisoformat(join_time_iso)
            
            # If user in DB is no longer in a VC, they left while bot was offline.
            if user_id not in current_vc_users:
                print(f"[RECONCILE] User {user_id} left while bot was offline. Logging time and closing session.")
                seconds = int((startup_time - join_time).total_seconds())
                if seconds > 0:
                    await db.execute("UPDATE voice_time SET seconds = seconds + ? WHERE user_id = ?", (seconds, user_id))
                await db.execute("DELETE FROM active_voice_sessions WHERE user_id = ?", (user_id,))

        await db.commit()

    # If user is in a VC but not in DB, they joined while bot was offline.
    async with aiosqlite.connect("server_data.db") as db:
        for user_id in current_vc_users:
            async with db.execute("SELECT 1 FROM active_voice_sessions WHERE user_id = ?", (user_id,)) as cursor:
                if await cursor.fetchone() is None:
                    print(f"[RECONCILE] User {user_id} joined while bot was offline. Starting new session.")
                    await db.execute("INSERT INTO active_voice_sessions (user_id, join_time_iso) VALUES (?, ?)", (user_id, startup_time.isoformat()))
        await db.commit()
    
    print("[SUCCESS] Voice state reconciliation complete.")
    # --- END NEW ---

    # ✅ NEW: Start the background task
    update_weekly_snapshot.start()

    bot.add_view(ApprovalView())
    bot.add_view(SuggestionStarterView())

    print("[SUCCESS] Bot is ready and persistent views are registered.")

@tasks.loop(hours=1)
async def update_weekly_snapshot():
    """
    Checks every hour if the previous week's leaderboard has been saved.
    If not, it calculates and stores a snapshot of the ranks.
    """
    # Determine the week string for LAST week
    today = datetime.utcnow()
    last_week_date = today - timedelta(days=7)
    previous_week_str = last_week_date.strftime("%Y-%W")

    async with aiosqlite.connect("server_data.db") as db:
        # Check if we have already processed this week
        async with db.execute("SELECT 1 FROM weekly_leaderboard_snapshot WHERE week = ?", (previous_week_str,)) as cursor:
            if await cursor.fetchone():
                # print(f"[DEBUG] Snapshot for week {previous_week_str} already exists.")
                return # We've already done this week, do nothing.

        print(f"[INFO] Generating new leaderboard snapshot for week {previous_week_str}...")

        # This query calculates the final leaderboard as of the end of the specified week
        snapshot_query = """
            WITH AllUserCumulativeTotals AS (
                SELECT
                    user_id,
                    SUM(count) as cumulative_messages
                FROM message_history
                WHERE week <= ?
                GROUP BY user_id
            ),
            RankedTotals AS (
                SELECT
                    user_id,
                    cumulative_messages,
                    RANK() OVER (ORDER BY cumulative_messages DESC) as rank
                FROM AllUserCumulativeTotals
            )
            SELECT user_id, rank, cumulative_messages FROM RankedTotals
        """
        
        cursor = await db.execute(snapshot_query, (previous_week_str,))
        snapshot_data = await cursor.fetchall()

        # Insert the snapshot data into the new table
        await db.executemany(
            "INSERT INTO weekly_leaderboard_snapshot (week, user_id, rank, total_messages) VALUES (?, ?, ?, ?)",
            [(previous_week_str, row[0], row[1], row[2]) for row in snapshot_data]
        )
        await db.commit()
        print(f"[SUCCESS] Saved leaderboard snapshot for week {previous_week_str} with {len(snapshot_data)} users.")

@update_weekly_snapshot.before_loop
async def before_update_weekly_snapshot():
    await bot.wait_until_ready() # Wait for the bot to be logged in before starting the loop

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    if message.channel.id not in EXCLUDED_CHANNEL_IDS:
        # Check if user sent another message within 3 seconds
        last_time = last_message_times.get(user_id, 0)
        if now - last_time >= 3:
            last_message_times[user_id] = now  # Update last valid message time

            # Message tracking
            async with aiosqlite.connect("server_data.db") as db:
                async with db.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()

                if row:
                    new_count = row[0] + 1
                    await db.execute("UPDATE messages SET count = ? WHERE user_id = ?", (new_count, user_id))
                else:
                    new_count = 1
                    await db.execute("INSERT INTO messages (user_id, count) VALUES (?, ?)", (user_id, 1))

                # ✅ CHANGE: Insert or update message count for the current week
                # This creates a string like "2023-45" (Year-WeekNumber)
                current_week = datetime.utcnow().strftime("%Y-%W")
                await db.execute("""
                    INSERT INTO message_history (user_id, week, count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, week) DO UPDATE SET count = count + 1
                """, (user_id, current_week))

                await db.commit()

            # Assign roles if needed
            await assign_roles(message.author, new_count, message.guild)

            # Candy drop (unchanged)
            if random.randint(1, 7000) == 1:
                async with aiosqlite.connect("server_data.db") as db:
                    async with db.execute("SELECT count FROM candies WHERE user_id = ?", (user_id,)) as cursor:
                        row = await cursor.fetchone()

                    if row:
                        new_candy_count = row[0] + 1
                        await db.execute("UPDATE candies SET count = ? WHERE user_id = ?", (new_candy_count, user_id))
                    else:
                        new_candy_count = 1
                        await db.execute("INSERT INTO candies (user_id, count) VALUES (?, ?)", (user_id, 1))

                    await db.commit()

                await message.channel.send(
                    f"# 🍭 CANDY DROP! 🍬\n"
                    f"{message.author.mention}, you got a **free candy** for chatting!\n"
                    f"You're now at **{new_candy_count}** total candies! ✨"
                )
                if new_candy_count >= 10:
                    CANDY_ROLE_NAME = "CANDY GOD"
                    role = discord.utils.get(message.guild.roles, name=CANDY_ROLE_NAME)
                    if role and role not in message.author.roles:
                        if message.guild.me.top_role > role and message.guild.me.guild_permissions.manage_roles:
                            await message.author.add_roles(role)
                            print(f"[DEBUG] Gave {CANDY_ROLE_NAME} role to {message.author.name}")
        else:
            pass
    
    await bot.process_commands(message)

async def assign_roles(member, count, guild):
    for threshold, role_name in MESSAGE_THRESHOLDS.items():
        if count >= threshold:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role not in member.roles:
                # ✅ Permission check before assigning the role
                if guild.me.top_role > role and guild.me.guild_permissions.manage_roles:
                    await member.add_roles(role)
                    print(f"[DEBUG] Gave role {role_name} to {member.name}")
                else:
                    print(f"[WARN] Missing permissions to assign {role_name} to {member.name}")

@bot.event
async def on_raw_reaction_add(payload):
    # Constants
    DEVELOPER_IDS = {265196052192165888, 849827666064048178} #switch to hector's id
    SUGGEST_REACTION = "☑️"
    BUG_EMOJI = "🐞"
    IDEA_EMOJI = "☑️"
    EXISTING_BOT_ID = 1361506233219158086
    POINT_THRESHOLD = 10

    BUG_CHANNEL_ID = 1298328050668408946
    IDEAS_CHANNEL_ID = 1295770322985025669
    #POINT_LOGS_CHANNEL = bot.get_channel(1392585590532341782)

    emoji_channel_map = {
        BUG_EMOJI: (BUG_CHANNEL_ID, "bug_pointed_messages", "bug_points", "Bug Finder"),
        IDEA_EMOJI: (IDEAS_CHANNEL_ID, "idea_pointed_messages", "idea_points", "Idea Contributor"),
    }

    TABLE_LABELS = {
        "suggest_points": "suggestion points",
        "bug_points": "bug points",
        "idea_points": "idea points"
    }

    # Ignore reactions from the dictionary bot
    if payload.user_id == EXISTING_BOT_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    channel = guild.get_channel(payload.channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return

    author = message.author

    # Suggestion system
    if payload.emoji.name == SUGGEST_REACTION and payload.channel_id in LANGUAGE_CHANNEL_IDS:
        if payload.user_id not in LANGUAGE_MOD_IDS:
            return  # Only award if a language mod added the ☑️
        if author.id in LANGUAGE_MOD_IDS:
            return  # Do not award if the author is a language mod
        if author.bot:
            return  # Do not award bots

        async with aiosqlite.connect("server_data.db") as db:
            # Prevent duplicate
            async with db.execute("SELECT 1 FROM suggest_pointed_messages WHERE message_id = ?", (payload.message_id,)) as cursor:
                already_pointed = await cursor.fetchone()

            if already_pointed:
                print(f"[DEBUG] Message {payload.message_id} already gave a suggestion point. Skipping.")
                return

            await db.execute("INSERT INTO suggest_pointed_messages (message_id) VALUES (?)", (payload.message_id,))

            # Update or insert points
            async with db.execute("SELECT count FROM suggest_points WHERE user_id = ?", (author.id,)) as cursor:
                row = await cursor.fetchone()

            if row:
                new_count = row[0] + 1
                await db.execute("UPDATE suggest_points SET count = ? WHERE user_id = ?", (new_count, author.id))
            else:
                new_count = 1
                await db.execute("INSERT INTO suggest_points (user_id, count) VALUES (?, ?)", (author.id, 1))

            await db.commit()
        return

    # Point-log editing
    if payload.channel_id == 1392585590532341782 and str(payload.emoji.name) == "✅":
        channel = await bot.fetch_channel(payload.channel_id)  # Fetches the channel properly

        if payload.user_id not in DEVELOPER_IDS:
            return  # Ignore if not from a developer

        channel = bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        lines = message.content.splitlines()
        if not lines:
            return

        first_line = lines[0]
        rest_of_message = "\n".join(lines[1:])

        if first_line.startswith("🐞"):
            # Extract mention from the line
            mention = message.mentions[0].mention if message.mentions else "the reporter"
            new_first_line = f"🟢 Fixed Bug, reported by {mention}"
        elif first_line.startswith("💡"):
            mention = message.mentions[0].mention if message.mentions else "the suggester"
            new_first_line = f"🟢 Implemented Idea by {mention}"
        else:
            new_first_line = "🟢 Handled"

        new_content = f"{new_first_line}\n{rest_of_message}"
        await message.edit(content=new_content)

    # Bug / Idea system
    if payload.user_id not in DEVELOPER_IDS:
        return

    if payload.emoji.name not in emoji_channel_map:
        return

    expected_channel_id, pointed_table, points_table, role_name = emoji_channel_map[payload.emoji.name]

    if payload.channel_id != expected_channel_id:
        return

    if author.bot:
        return

    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute(f"SELECT 1 FROM {pointed_table} WHERE message_id = ?",
                              (payload.message_id,)) as cursor:
            already_pointed = await cursor.fetchone()

        if already_pointed:
            print(f"[DEBUG] Message {payload.message_id} already gave a point in {pointed_table}. Skipping.")
            return

        await db.execute(f"INSERT INTO {pointed_table} (message_id) VALUES (?)", (payload.message_id,))

        async with db.execute(f"SELECT count FROM {points_table} WHERE user_id = ?", (author.id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            new_count = row[0] + 1
            await db.execute(f"UPDATE {points_table} SET count = ? WHERE user_id = ?", (new_count, author.id))
        else:
            new_count = 1
            await db.execute(f"INSERT INTO {points_table} (user_id, count) VALUES (?, ?)", (author.id, 1))

        await db.commit()

    print(f"[DEBUG] {author} now has {new_count} points in {points_table}.")
    #label = TABLE_LABELS.get(points_table, points_table)  # fallback to raw name if not found
    #await POINT_LOGS_CHANNEL.send(f"✅ {role_name} point recorded for {display_name}! {display_name} now has {new_count} {label}.")

    indented_content = '\n'.join(f"> {line}" for line in message.content.splitlines())

    if payload.emoji.name == BUG_EMOJI:
        if POINT_LOGS_CHANNEL:
            await POINT_LOGS_CHANNEL.send(
                f"🐞 **Bug Reported** by {author.mention}:\n"
                f"{indented_content}\n"
                f"🔗 {message.jump_url}\n"
            )
    elif payload.emoji.name == IDEA_EMOJI:
        if POINT_LOGS_CHANNEL:
            await POINT_LOGS_CHANNEL.send(
                f"💡 **Approved Idea** by {author.mention}:\n"
                f"{indented_content}\n"
                f"🔗 {message.jump_url}\n"
            )

    if new_count >= POINT_THRESHOLD:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(author.id)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
                print(f"[DEBUG] {member.name} was given the '{role.name}' role.")
            except discord.Forbidden:
                print(f"[WARN] Bot doesn't have permission to assign the '{role.name}' role to {member.name}. Skipping.")
            except discord.HTTPException as e:
                print(f"[ERROR] Unexpected error when assigning role: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    # Ignore updates from bots
    if member.bot:
        return

    # Use the 'from datetime import datetime' for consistency with your code
    now = datetime.utcnow()

    # --- HANDLING LEAVE or MOVE ---
    # This block executes if the user was in a valid channel before the update.
    if before.channel and before.channel.id not in EXCLUDED_VC_IDS:
        async with aiosqlite.connect("server_data.db") as db:
            # 1. Find the user's join session in the database.
            cursor = await db.execute("SELECT join_time_iso FROM active_voice_sessions WHERE user_id = ?", (member.id,))
            session_row = await cursor.fetchone()

            # If a session exists, calculate the time and delete the session record.
            if session_row:
                join_time = datetime.fromisoformat(session_row[0])
                duration_seconds = int((now - join_time).total_seconds())

                # 2. Add the calculated time to the main `voice_time` table.
                # This "UPSERT" command updates the record if the user exists, or inserts a new one if they don't.
                if duration_seconds > 0:
                    await db.execute("""
                        INSERT INTO voice_time (user_id, seconds) VALUES (?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET seconds = seconds + excluded.seconds
                    """, (member.id, duration_seconds))

                # 3. Clean up by deleting the temporary session record.
                await db.execute("DELETE FROM active_voice_sessions WHERE user_id = ?", (member.id,))
                await db.commit()

    # --- HANDLING JOIN or MOVE ---
    # This block executes if the user is in a valid channel after the update.
    if after.channel and after.channel.id not in EXCLUDED_VC_IDS:
        async with aiosqlite.connect("server_data.db") as db:
            # Create a new session record with the current time.
            # INSERT OR IGNORE is used for safety to prevent errors if a session somehow already exists.
            # When a user moves VCs, the LEAVE logic runs first, deleting the old session,
            # and then this JOIN logic runs, creating a new one.
            await db.execute("INSERT OR IGNORE INTO active_voice_sessions (user_id, join_time_iso) VALUES (?, ?)", (member.id, now.isoformat()))
            await db.commit()

class LeaderboardView(discord.ui.View):
    def __init__(self, author_id, current_category, page, total_pages, entries):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.current_category = current_category
        self.page = page
        self.total_pages = total_pages
        self.entries = entries

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("These buttons aren't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Messages", style=discord.ButtonStyle.primary, custom_id="category_messages")
    async def messages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "messages", 1, self.author_id)

    @discord.ui.button(label="Bugs", style=discord.ButtonStyle.primary, custom_id="category_bugs")
    async def bugs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "bugs", 1, self.author_id)

    @discord.ui.button(label="Ideas", style=discord.ButtonStyle.primary, custom_id="category_ideas")
    async def ideas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "ideas", 1, self.author_id)

    @discord.ui.button(label="Suggestions", style=discord.ButtonStyle.primary, custom_id="category_suggestions")
    async def suggestions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "suggestions", 1, self.author_id)

    @discord.ui.button(label="Voice", style=discord.ButtonStyle.primary, custom_id="category_voice")
    async def voice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "voice", 1, self.author_id)

async def update_leaderboard(ctx_or_interaction, category, page, author_id):
    table_map = {
        "suggestions": "suggest_points",
        "messages": "messages",
        "bugs": "bug_points",
        "ideas": "idea_points",
        "voice": "voice_time"
    }

    label_map = {
        "suggestions": ("suggestion", "suggestions"),
        "messages": ("message", "messages"),
        "bugs": ("bug found", "bugs found"),
        "ideas": ("idea", "ideas"),
        "voice": ("second", "seconds")
    }

    if category not in table_map:
        await ctx_or_interaction.response.send_message(
            "Invalid category. Use: suggestions, messages, bugs, ideas.",
            ephemeral=True
        )
        return

    table = table_map[category]

    async with aiosqlite.connect("server_data.db") as db:
        time_column = "seconds" if category == "voice" else "count"
        async with db.execute(f"SELECT user_id, {time_column} FROM {table} ORDER BY {time_column} DESC") as cursor:
            full_rows = await cursor.fetchall()

    total_entries = len(full_rows)
    top_9 = full_rows[:9]

    # Find author's index/rank if present
    author_index = None
    for i, (uid, _) in enumerate(full_rows):
        if str(uid) == str(author_id):
            author_index = i
            break

    author_rank = author_index + 1 if author_index is not None else None
    author_points = full_rows[author_index][1] if author_index is not None else 0

    lines = []

    # Show top 9 entries
    for i, (user_id, count) in enumerate(top_9, start=1):
        member = ctx_or_interaction.guild.get_member(user_id)
        if member:
            username = member.display_name
        else:
            user = await bot.fetch_user(user_id)
            username = user.name if user else f"User {user_id}"

        singular, plural = label_map[category]
        if category == "voice":
            hours = count // 3600
            minutes = (count % 3600) // 60
            seconds = count % 60
            time_str = f"{hours}h {minutes}m {seconds}s"
            line = f"{i}. {'➤ ' if user_id == author_id else ''}{username} • **{time_str}**"
        else:
            unit = singular if count == 1 else plural
            line = f"{i}. {'➤ ' if user_id == author_id else ''}{username} • **{count} {unit}**"

        lines.append(line)

    # Now decide what to show in the last line:
    if author_rank is None or author_rank <= 9:
        # Show 10th place normally if it exists
        if total_entries > 9:
            user_id, count = full_rows[9]
            member = ctx_or_interaction.guild.get_member(user_id)
            if member:
                username = member.display_name
            else:
                user = await bot.fetch_user(user_id)
                username = user.name if user else f"User {user_id}"

            singular, plural = label_map[category]
            if category == "voice":
                hours = count // 3600
                minutes = (count % 3600) // 60
                seconds = count % 60
                time_str = f"{hours}h {minutes}m {seconds}s"
                line = f"10. {username} • **{time_str}**"
            else:
                unit = singular if count == 1 else plural
                line = f"10. {username} • **{count} {unit}**"

            if user_id == author_id:
                if category == "voice":
                    line = f"{author_rank}. {username} • **{time_str}**"
                else:
                    line = f"{author_rank}. {username} • **{count} {unit}**"
            lines.append(line)
    else:
        # User is ranked but not in top 9 → show user's real position
        if author_points > 0:
            member = ctx_or_interaction.guild.get_member(author_id)
            if member:
                username = member.display_name
            else:
                user = await bot.fetch_user(author_id)
                username = user.name if user else f"User {author_id}"

            if category == "voice":
                hours = author_points // 3600
                minutes = (author_points % 3600) // 60
                seconds = author_points % 60
                time_str = f"{hours}h {minutes}m {seconds}s"
                line = f"...\n➤ {author_rank}.\u200B {username} • **{time_str}**"
            else:
                singular, plural = label_map[category]
                unit = singular if author_points == 1 else plural
                line = f"...\n➤ {author_rank}.\u200B {username} • **{author_points} {unit}**"

            lines.append(line)
        else:
            lines.append("*You are currently unranked.*")

    description = "\n".join(lines)

    embed = discord.Embed(
        title=f"🏆 {category.capitalize()} Leaderboard",
        description=description,
        color=discord.Color.gold()
    )

    view = LeaderboardView(author_id, category, page, 1, full_rows)

    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.response.edit_message(embed=embed, view=view)
    else:
        await ctx_or_interaction.send(embed=embed, view=view)

@bot.command(name="l", aliases=["leaderboard", "leaderboards", "lb"])
async def l(ctx, category: str = "messages"):
    await update_leaderboard(ctx, category.lower(), 1, ctx.author.id)

@bot.command(name="help")
async def show_help(ctx):

    embed = discord.Embed(
        title="📚 Server Commands Overview",
        description="Here are the commands from our Word Bomb bots in this server:",
        color=discord.Color.blue()
    )

    for bot_name, cmds in OTHER_BOTS_COMMANDS.items():
        if cmds:
            command_list = "\n".join(cmds)
            embed.add_field(name=bot_name, value=command_list, inline=False)

    await ctx.send(embed=embed)

@bot.command(name="give")
async def give_time(ctx, member: discord.Member, seconds: int):
    ALLOWED_USER_ID = 849827666064048178  # Change this to the allowed user's ID

    if ctx.author.id != ALLOWED_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return

    if seconds <= 0:
        await ctx.send("❌ Please enter a positive number of seconds.")
        return

    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            total = row[0] + seconds
            await db.execute("UPDATE voice_time SET seconds = ? WHERE user_id = ?", (total, member.id))
        else:
            total = seconds
            await db.execute("INSERT INTO voice_time (user_id, seconds) VALUES (?, ?)", (member.id, seconds))

        await db.commit()

    hours = total // 3600
    minutes = (total % 3600) // 60
    sec = total % 60
    await ctx.send(f"✅ Added `{seconds}` seconds to {member.mention}. New total: **{hours}h {minutes}m {sec}s**")

# Trivia Game
class QuestionSuggestionModal(Modal, title='Suggest a New Question'):
    def __init__(self, bot, approval_channel):
        super().__init__()
        self.bot = bot
        self.approval_channel = approval_channel
        self.valid_languages = {"en-US", "pt-BR", "tr-TR", "fr-FR", "es-ES", "tl-TL", "de-DE", "it-IT", "id-ID",
                                "sv-SE", "ru", "ca-CA", "fi", "nl", "mc-MC"}
        self.valid_difficulties = {"easy", "normal", "hard"}

    language = TextInput(
        label="Language / Locale Code",
        style=discord.TextStyle.short,
        placeholder="e.g., en-US, pt-BR, fr-FR...",
        required=True,
        max_length=10,
    )

    difficulty = TextInput(
        label="Difficulty",
        style=discord.TextStyle.short,
        placeholder="easy, normal, or hard",
        required=True,
        max_length=10,
    )

    question_text = TextInput(
        label='Question',
        style=discord.TextStyle.paragraph,
        placeholder='e.g., What is the capital of France?',
        required=True,
        max_length=256,
    )

    correct_answer = TextInput(
        label='Correct Answer',
        style=discord.TextStyle.short,
        placeholder='e.g., Paris',
        required=True,
        max_length=100,
    )

    other_answers = TextInput(
        label='Three Incorrect Answers (separate with comma)',
        style=discord.TextStyle.paragraph,
        placeholder='e.g., London, Berlin, Rome',
        required=True,
        max_length=300,
    )

    # --- NOTE FIELDS HAVE BEEN REMOVED ---

    async def on_submit(self, interaction: discord.Interaction):
        lang_input = self.language.value.strip()
        diff_input = self.difficulty.value.lower().strip()

        if lang_input not in self.valid_languages:
            await interaction.response.send_message(
                f"❌ **Invalid Locale:** Please use a valid code like `en-US`, `pt-BR`, etc.",
                ephemeral=True
            )
            return

        if diff_input not in self.valid_difficulties:
            await interaction.response.send_message(
                f"❌ **Invalid Difficulty:** Please enter `easy`, `normal`, or `hard`.",
                ephemeral=True
            )
            return

        incorrect_answers = [ans.strip() for ans in self.other_answers.value.split(',') if ans.strip()]
        if len(incorrect_answers) != 3:
            await interaction.response.send_message(
                "❌ **Error:** Please provide exactly three incorrect answers, separated by a comma.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Thank you, {interaction.user.mention}! Your suggestion is submitted for review.",
            ephemeral=True
        )

        embed = discord.Embed(
            title=f"New Question Suggestion",
            description=f"**Submitted by:** {interaction.user.mention} (`{interaction.user.id}`)",
            color=discord.Color.orange()
        )
        embed.add_field(name="Locale", value=f"`{lang_input}`", inline=True)
        embed.add_field(name="Difficulty", value=f"`{diff_input}`", inline=True)
        embed.add_field(name="Question", value=self.question_text.value, inline=False)
        embed.add_field(name="✅ Correct Answer", value=self.correct_answer.value, inline=False)
        embed.add_field(name="❌ Incorrect Answers", value="\n".join(f"- {ans}" for ans in incorrect_answers),
                        inline=False)

        # --- REMOVED THE NOTE FIELDS FROM THE EMBED ---

        embed.set_footer(text="Awaiting review from a Language Moderator...")
        await self.approval_channel.send(embed=embed, view=ApprovalView())

# ADD THIS NEW VIEW CLASS
class SuggestionStarterView(ui.View):
    def __init__(self):
        # timeout=None makes the button persistent
        super().__init__(timeout=None)

    @ui.button(label='Suggest a Question', style=discord.ButtonStyle.blurple, custom_id='start_suggestion')
    async def start_suggestion_button(self, interaction: discord.Interaction, button: ui.Button):
        # This is the code that runs when a user clicks the button
        approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
        if not approval_channel:
            # Send a user-facing error if the admin setup is wrong
            await interaction.response.send_message("Error: Approval channel not configured. Please contact an admin.",
                                                    ephemeral=True)
            return

        # This opens the pop-up modal for the user who clicked
        await interaction.response.send_modal(QuestionSuggestionModal(bot, approval_channel))


# ADD THIS NEW ADMIN COMMAND
@bot.command(name="setup_suggestions")
async def setup_suggestions(ctx):

    if ctx.author.id != 849827666064048178:  # Replace with your actual Discord user ID
        await ctx.send("You don't have permission to use this command.")
        return

    """Sends the persistent message with the 'Suggest a Question' button."""
    channel_id = 1395207538445910047  # The channel where the button will live
    target_channel = bot.get_channel(channel_id)

    if not target_channel:
        await ctx.send("Error: Could not find the target channel.")
        return

    embed = discord.Embed(
        title="❓ Help Create the Trivia Game!",
        description="Have a great trivia question? Click the button below to suggest it!\n\n"
                    "Your question will be reviewed by our Language Moderators. If approved, "
                    "it will be added to the new game mode for everyone to enjoy.",
        color=discord.Color.blue()
    )

    # Send the message to the channel with the button view
    await target_channel.send(embed=embed, view=SuggestionStarterView())
    await ctx.send(f"✅ Suggestion button message has been sent to {target_channel.mention}.")


class ApprovalView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Approve', style=discord.ButtonStyle.green, custom_id='question_approve')
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in LANGUAGE_MOD_IDS and interaction.user.id != 849827666064048178:
            await interaction.response.send_message("❌ You do not have permission to approve suggestions.",
                                                    ephemeral=True)
            return

        original_embed = interaction.message.embeds[0]

        try:
            locale = next(field.value for field in original_embed.fields if field.name == "Locale").strip('`')
            difficulty_str = next(field.value for field in original_embed.fields if field.name == "Difficulty").strip(
                '`')
            question = next(field.value for field in original_embed.fields if field.name == "Question")
            correct_answer = next(field.value for field in original_embed.fields if field.name == "✅ Correct Answer")

            incorrect_answers_str = next(
                field.value for field in original_embed.fields if field.name == "❌ Incorrect Answers")
            incorrect_answers = [line.lstrip('- ') for line in incorrect_answers_str.split('\n')]

            submitter_id = original_embed.description.split('`')[1]

        except (StopIteration, IndexError) as e:
            await interaction.response.send_message(f"Error parsing the embed data: {e}", ephemeral=True)
            return

        difficulty_map = {"easy": 0, "normal": 1, "hard": 2}
        difficulty_int = difficulty_map.get(difficulty_str, 1)

        all_answers = [correct_answer] + incorrect_answers
        right_answer_index = all_answers.index(correct_answer)

        # --- UPDATED: 'nf' and 'ns' are now saved as empty strings ---
        question_document = {
            "q": question,
            "a": all_answers,
            "r": right_answer_index,
            "nf": "",  # Fail note is now an empty placeholder
            "ns": "",  # Success note is now an empty placeholder
            "u": submitter_id,
            "l": locale,
            "d": difficulty_int
        }

        await questions_collection.insert_one(question_document)

        new_embed = original_embed
        new_embed.color = discord.Color.green()
        new_embed.set_footer(text=f"✅ Approved by {interaction.user.display_name}")

        self.approve_button.disabled = True
        self.decline_button.disabled = True
        await interaction.response.edit_message(embed=new_embed, view=self)

    # --- The decline_button method does not need to be changed ---
    @ui.button(label='Decline', style=discord.ButtonStyle.red, custom_id='question_decline')
    async def decline_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in LANGUAGE_MOD_IDS and interaction.user.id != 849827666064048178:
            await interaction.response.send_message("❌ You do not have permission to decline suggestions.",
                                                    ephemeral=True)
            return

        original_embed = interaction.message.embeds[0]
        new_embed = original_embed
        new_embed.color = discord.Color.red()
        new_embed.set_footer(text=f"❌ Declined by {interaction.user.display_name}")

        self.approve_button.disabled = True
        self.decline_button.disabled = True
        await interaction.response.edit_message(embed=new_embed, view=self)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        perms = ', '.join(error.missing_permissions)
        await ctx.send(
            f"Error in command `{ctx.command}`: You are missing `{perms}` permission(s) to run this command.",
            delete_after=8
        )
    else:
        # Log unexpected errors without crashing the bot
        print(f"[ERROR] Unexpected error in command {ctx.command}: {error}")

bot.run(token)
