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
rejected_questions_collection = None


@bot.event
async def on_ready():
    global client, db, questions_collection, rejected_questions_collection
    print("[INFO] Initializing MongoDB connection...")
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        db = client.questions
        questions_collection = db.approved

        # --- THIS IS THE MISSING LINE ---
        rejected_questions_collection = db.rejected

        await client.admin.command('ismaster')
        print("[SUCCESS] MongoDB connection established.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        return

    global POINT_LOGS_CHANNEL
    POINT_LOGS_CHANNEL = bot.get_channel(1392585590532341782)
    if POINT_LOGS_CHANNEL:
        print(f"[DEBUG] POINT_LOGS_CHANNEL loaded: {POINT_LOGS_CHANNEL.name} ({POINT_LOGS_CHANNEL.id})")
    else:
        print("[ERROR] POINT_LOGS_CHANNEL could not be loaded.")

    print(f"[DEBUG] Bot is ready. Logged in as {bot.user} ({bot.user.id})")

    async with aiosqlite.connect("server_data.db") as db_sqlite:
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS messages (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS bug_points (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS idea_points (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS voice_time (user_id INTEGER PRIMARY KEY, seconds INTEGER NOT NULL)")
        await db_sqlite.execute("CREATE TABLE IF NOT EXISTS bug_pointed_messages (message_id INTEGER PRIMARY KEY)")
        await db_sqlite.execute("CREATE TABLE IF NOT EXISTS idea_pointed_messages (message_id INTEGER PRIMARY KEY)")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS candies (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS message_history (user_id INTEGER, week TEXT, count INTEGER, PRIMARY KEY (user_id, week))")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS weekly_leaderboard_snapshot (week TEXT, user_id INTEGER, rank INTEGER, total_messages INTEGER, PRIMARY KEY (week, user_id))")
        await db_sqlite.execute(
            "CREATE TABLE IF NOT EXISTS active_voice_sessions (user_id INTEGER PRIMARY KEY, join_time_iso TEXT NOT NULL)")

        # ✅ --- NEW TABLE ---
        # This table will permanently store every completed voice session for historical analysis.
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS voice_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_timestamp TEXT NOT NULL,
                end_timestamp TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL
            )
        """)
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS bug_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER UNIQUE,
                report_timestamp TEXT NOT NULL,
                description TEXT
            )
        """)
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS idea_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER UNIQUE,
                submission_timestamp TEXT NOT NULL,
                description TEXT
            )
        """)

        await db_sqlite.commit()

    print("[INFO] Reconciling voice states on startup...")
    startup_time = datetime.utcnow()
    current_vc_users = set()
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.id not in EXCLUDED_VC_IDS:
                for member in channel.members:
                    if not member.bot:
                        current_vc_users.add(member.id)
    async with aiosqlite.connect("server_data.db") as db_sqlite:
        cursor = await db_sqlite.execute("SELECT user_id, join_time_iso FROM active_voice_sessions")
        db_sessions = await cursor.fetchall()
        for user_id, join_time_iso in db_sessions:
            join_time = datetime.fromisoformat(join_time_iso)
            if user_id not in current_vc_users:
                print(f"[RECONCILE] User {user_id} left while bot was offline.")
                seconds = int((startup_time - join_time).total_seconds())
                if seconds > 0:
                    await db_sqlite.execute("UPDATE voice_time SET seconds = seconds + ? WHERE user_id = ?",
                                            (seconds, user_id))
                await db_sqlite.execute("DELETE FROM active_voice_sessions WHERE user_id = ?", (user_id,))
        await db_sqlite.commit()
    async with aiosqlite.connect("server_data.db") as db_sqlite:
        for user_id in current_vc_users:
            async with db_sqlite.execute("SELECT 1 FROM active_voice_sessions WHERE user_id = ?", (user_id,)) as cursor:
                if await cursor.fetchone() is None:
                    print(f"[RECONCILE] User {user_id} joined while bot was offline.")
                    await db_sqlite.execute("INSERT INTO active_voice_sessions (user_id, join_time_iso) VALUES (?, ?)",
                                            (user_id, startup_time.isoformat()))
        await db_sqlite.commit()
    print("[SUCCESS] Voice state reconciliation complete.")
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
    DEVELOPER_IDS = {265196052192165888, 849827666064048178}
    BUG_EMOJI = "🐞"
    IDEA_EMOJI = "☑️"
    EXISTING_BOT_ID = 1361506233219158086
    POINT_THRESHOLD = 10
    BUG_CHANNEL_ID = 1298328050668408946
    IDEAS_CHANNEL_ID = 1295770322985025669

    emoji_channel_map = {
        BUG_EMOJI: (BUG_CHANNEL_ID, "bug_pointed_messages", "bug_points", "Bug Finder"),
        IDEA_EMOJI: (IDEAS_CHANNEL_ID, "idea_pointed_messages", "idea_points", "Idea Contributor"),
    }

    if payload.user_id == EXISTING_BOT_ID: return
    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    channel = guild.get_channel(payload.channel_id)
    if not channel: return
    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return
    author = message.author

    # --- THE OLD SUGGESTION SYSTEM LOGIC HAS BEEN REMOVED FROM HERE ---

    # Point-log editing
    if payload.channel_id == 1392585590532341782 and str(payload.emoji.name) == "✅":
        if payload.user_id not in DEVELOPER_IDS: return
        try:
            message_to_edit = await channel.fetch_message(payload.message_id)
        except Exception:
            return
        lines = message_to_edit.content.splitlines()
        if not lines: return
        first_line, rest_of_message = lines[0], "\n".join(lines[1:])
        mention = message_to_edit.mentions[0].mention if message_to_edit.mentions else "the user"
        if first_line.startswith("🐞"): new_first_line = f"🟢 Fixed Bug, reported by {mention}"
        elif first_line.startswith("💡"): new_first_line = f"🟢 Implemented Idea by {mention}"
        else: new_first_line = "🟢 Handled"
        await message_to_edit.edit(content=f"{new_first_line}\n{rest_of_message}")

    # Bug / Idea system
    if payload.user_id not in DEVELOPER_IDS: return
    if payload.emoji.name not in emoji_channel_map: return
    expected_channel_id, pointed_table, points_table, role_name = emoji_channel_map[payload.emoji.name]
    if payload.channel_id != expected_channel_id or author.bot: return

    # ✅ --- REPLACEMENT LOGIC FOR POINT AWARDING ---
    async with aiosqlite.connect("server_data.db") as db:
        # First, check if this message already gave a point.
        async with db.execute(f"SELECT 1 FROM {pointed_table} WHERE message_id = ?", (payload.message_id,)) as cursor:
            if await cursor.fetchone():
                print(f"[DEBUG] Message {payload.message_id} already processed. Skipping.")
                return

        # Mark this message as processed to prevent duplicate points.
        await db.execute(f"INSERT INTO {pointed_table} (message_id) VALUES (?)", (payload.message_id,))

        # --- NEW LOGIC FOR BUG REPORTS ---
        if payload.emoji.name == BUG_EMOJI:
            # 1. Log the detailed report to the new historical table.
            report_timestamp = datetime.utcnow().isoformat()
            # Store the first 200 characters of the message as a description.
            report_description = message.content[:200]

            await db.execute("""
                    INSERT INTO bug_reports (user_id, message_id, report_timestamp, description)
                    VALUES (?, ?, ?, ?)
                """, (author.id, payload.message_id, report_timestamp, report_description))

        # ✅ --- NEW LOGIC FOR IDEA SUBMISSIONS ---
        if payload.emoji.name == IDEA_EMOJI:
            submission_timestamp = datetime.utcnow().isoformat()
            submission_description = message.content[:200]
            await db.execute("""
                    INSERT INTO idea_submissions (user_id, message_id, submission_timestamp, description)
                    VALUES (?, ?, ?, ?)
                """, (author.id, payload.message_id, submission_timestamp, submission_description))

        # --- KEEPING THE LEADERBOARD IN SYNC ---
        # 2. Update the old cumulative points table for the !l command.
        await db.execute(f"""
                INSERT INTO {points_table} (user_id, count) VALUES (?, 1)
                ON CONFLICT(user_id) DO UPDATE SET count = count + 1
            """, (author.id,))

        # Get the new total count for role assignment.
        async with db.execute(f"SELECT count FROM {points_table} WHERE user_id = ?", (author.id,)) as cursor:
            row = await cursor.fetchone()
            new_count = row[0] if row else 1

        await db.commit()

    print(f"[DEBUG] {author} now has {new_count} points in {points_table}.")
    indented_content = '\n'.join(f"> {line}" for line in message.content.splitlines())
    if payload.emoji.name == BUG_EMOJI:
        if POINT_LOGS_CHANNEL: await POINT_LOGS_CHANNEL.send(f"🐞 **Bug Reported** by {author.mention}:\n{indented_content}\n🔗 {message.jump_url}\n")
    elif payload.emoji.name == IDEA_EMOJI:
        if POINT_LOGS_CHANNEL: await POINT_LOGS_CHANNEL.send(f"💡 **Approved Idea** by {author.mention}:\n{indented_content}\n🔗 {message.jump_url}\n")
    if new_count >= POINT_THRESHOLD:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(author.id)
        if role and role not in member.roles:
            try:
                await member.add_roles(role)
                print(f"[DEBUG] {member.name} was given the '{role.name}' role.")
            except discord.Forbidden:
                print(f"[WARN] Bot doesn't have permission to assign the '{role.name}' role.")

@bot.event
async def on_voice_state_update(member, before, after):
    # Ignore updates from other bots
    if member.bot:
        return

    now = datetime.utcnow()

    # --- HANDLING A USER LEAVING A VOICE CHANNEL ---
    # This block runs if the user was in a valid channel before the update,
    # but is no longer in one (or moved to an excluded channel).
    if before.channel and before.channel.id not in EXCLUDED_VC_IDS:
        # Check if the user is truly leaving (not just moving to another valid channel)
        if not after.channel or after.channel.id in EXCLUDED_VC_IDS:
            async with aiosqlite.connect("server_data.db") as db:
                # 1. Find the user's active session to get their join time.
                cursor = await db.execute("SELECT join_time_iso FROM active_voice_sessions WHERE user_id = ?", (member.id,))
                session_row = await cursor.fetchone()

                if session_row:
                    # 2. Calculate the session duration.
                    join_time = datetime.fromisoformat(session_row[0])
                    duration_seconds = int((now - join_time).total_seconds())

                    # 3. Log the completed session to our new permanent table.
                    if duration_seconds > 5: # Only log sessions longer than 5 seconds
                        await db.execute("""
                            INSERT INTO voice_sessions (user_id, start_timestamp, end_timestamp, duration_seconds)
                            VALUES (?, ?, ?, ?)
                        """, (member.id, join_time.isoformat(), now.isoformat(), duration_seconds))

                        await db.execute("""
                            INSERT INTO voice_time (user_id, seconds) VALUES (?, ?)
                            ON CONFLICT(user_id) DO UPDATE SET seconds = seconds + excluded.seconds
                        """, (member.id, duration_seconds))

                    # 4. Clean up the temporary active session record.
                    await db.execute("DELETE FROM active_voice_sessions WHERE user_id = ?", (member.id,))
                    await db.commit()


    # --- HANDLING A USER JOINING A VOICE CHANNEL ---
    # This block runs if the user is in a valid channel after the update.
    if after.channel and after.channel.id not in EXCLUDED_VC_IDS:
        async with aiosqlite.connect("server_data.db") as db:
            # Create a new temporary session record with the current time.
            # "INSERT OR IGNORE" prevents errors if a session somehow already exists.
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

        # --- THIS IS THE NEW ADDITION ---
        # 1. Construct the unique URL for the user who ran the command.
        profile_url = f"https://discord.wordbomb.io/user/{self.author_id}"

        # 2. Create a special "link" button.
        #    - style=discord.ButtonStyle.link is required for URL buttons.
        #    - We provide a 'url' instead of a 'custom_id'.
        #    - We put it on row=1 to place it below the category buttons.
        profile_button = discord.ui.Button(
            label="View Web Profile",
            style=discord.ButtonStyle.link,
            url=profile_url,
            emoji="🌐",  # A nice globe emoji for a web link
            row=1
        )

        # 3. Add the new button to the view.
        self.add_item(profile_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("These buttons aren't for you!", ephemeral=True)
            return False
        return True

    # All of your existing category buttons remain exactly the same.
    # The 'row=0' parameter is implicitly set for decorated buttons.
    @discord.ui.button(label="Messages", style=discord.ButtonStyle.primary, custom_id="category_messages")
    async def messages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "messages", 1, self.author_id)

    @discord.ui.button(label="Trivia", style=discord.ButtonStyle.primary, custom_id="category_trivias")
    async def trivia_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "trivia", 1, self.author_id)

    @discord.ui.button(label="Bugs", style=discord.ButtonStyle.primary, custom_id="category_bugs")
    async def bugs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "bugs", 1, self.author_id)

    @discord.ui.button(label="Ideas", style=discord.ButtonStyle.primary, custom_id="category_ideas")
    async def ideas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "ideas", 1, self.author_id)

    @discord.ui.button(label="Voice", style=discord.ButtonStyle.primary, custom_id="category_voice")
    async def voice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "voice", 1, self.author_id)

async def update_leaderboard(ctx_or_interaction, category, page, author_id):
    # This map can be simplified now that "suggestions" is gone
    table_map = {
        "messages": "messages",
        "bugs": "bug_points",
        "ideas": "idea_points",
        "voice": "voice_time"
    }
    # I've renamed "questions" to "trivia" to match your code
    label_map = {
        "trivia": ("question suggested", "questions suggested"),
        "messages": ("message", "messages"),
        "bugs": ("bug found", "bugs found"),
        "ideas": ("idea", "ideas"),
        "voice": ("second", "seconds")
    }

    full_rows = []

    # This assumes your bot is already saving rejected questions to a 'rejected_questions_collection'
    # as we set up in the previous step.
    if category == "trivia":
        if questions_collection is not None and rejected_questions_collection is not None:
            # --- THIS IS THE NEW, CORRECTED PIPELINE ---
            pipeline = [
                # Stage 1: Merge all documents from the 'rejected' collection into our pipeline.
                # Now the pipeline contains documents from BOTH 'approved' and 'rejected'.
                {
                    "$unionWith": {
                        "coll": "rejected"  # The name of the other collection to include
                    }
                },
                # Stage 2: Group all the combined documents by user ID ('u').
                {
                    "$group": {
                        "_id": "$u",
                        "count": {"$sum": 1}  # Count 1 for each document (approved or rejected)
                    }
                },
                # Stage 3: Sort the results to find the top contributors.
                {
                    "$sort": {
                        "count": -1
                    }
                }
            ]
            # We start the pipeline on one collection, and $unionWith brings in the other.
            cursor = questions_collection.aggregate(pipeline)
            full_rows = [(doc["_id"], doc["count"]) async for doc in cursor]
        else:
            error_message = "The trivia leaderboard is currently unavailable. Please try again later."
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(error_message, ephemeral=True)
            else:
                await ctx_or_interaction.send(error_message)
            return
    else:
        # This part for SQLite leaderboards remains unchanged.
        if category not in table_map:
            await ctx_or_interaction.response.send_message("Invalid category.", ephemeral=True)
            return
        table = table_map[category]
        async with aiosqlite.connect("server_data.db") as db:
            time_column = "seconds" if category == "voice" else "count"
            async with db.execute(f"SELECT user_id, {time_column} FROM {table} ORDER BY {time_column} DESC") as cursor:
                full_rows = await cursor.fetchall()

    total_entries = len(full_rows)
    author_id_str = str(author_id)
    author_index = next((i for i, (uid, _) in enumerate(full_rows) if str(uid) == author_id_str), None)
    author_rank = author_index + 1 if author_index is not None else None
    author_points = full_rows[author_index][1] if author_index is not None else 0
    lines = []
    top_entries = full_rows[:10]
    for i, (user_id, count) in enumerate(top_entries, start=1):
        try:
            member = ctx_or_interaction.guild.get_member(int(user_id))
            username = member.display_name if member else (await bot.fetch_user(int(user_id))).name
        except (ValueError, discord.NotFound):
            username = f"Unknown User ({user_id})"
        singular, plural = label_map[category]
        unit = plural if count != 1 else singular
        display_count = f"{count // 3600}h {(count % 3600) // 60}m {count % 60}s" if category == "voice" else f"{count} {unit}"
        line = f"{i}. {'➤ ' if str(user_id) == author_id_str else ''}{username} • **{display_count}**"
        lines.append(line)
    if author_rank and author_rank > 10 and author_points > 0:
        member = ctx_or_interaction.guild.get_member(author_id)
        username = member.display_name if member else f"User ID: {author_id}"
        singular, plural = label_map[category]
        unit = plural if author_points != 1 else singular
        display_points = f"{author_points // 3600}h {(author_points % 3600) // 60}m {author_points % 60}s" if category == "voice" else f"{author_points} {unit}"
        lines.append(f"...\n➤ {author_rank}. {username} • **{display_points}**")
    description = "\n".join(lines) if lines else "This leaderboard is currently empty!"
    embed = discord.Embed(title=f"🏆 {category.capitalize()} Leaderboard", description=description,
                          color=discord.Color.gold())
    view = LeaderboardView(author_id, category, 1, 1, full_rows)
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
        self.language_map = {
            "english": "en-US", "portuguese": "pt-BR", "turkish": "tr-TR",
            "french": "fr-FR", "spanish": "es-ES", "tagalog": "tl-TL",
            "german": "de-DE", "italian": "it-IT", "indonesian": "id-ID",
            "swedish": "sv-SE", "russian": "ru", "catalan": "ca-CA",
            "finnish": "fi", "dutch": "nl", "minecraft": "mc-MC"
        }
        self.valid_difficulties = {"easy", "normal", "hard", "insane"}

    language = TextInput(
        label="Language",
        style=discord.TextStyle.short,
        placeholder="e.g., English, French, Spanish...",
        required=True,
        max_length=20,
    )

    difficulty = TextInput(
        label="Difficulty",
        style=discord.TextStyle.short,
        placeholder="easy, normal, hard, or insane",
        required=True,
        max_length=10,
    )

    question_text = TextInput(
        label='Question',
        style=discord.TextStyle.paragraph,
        placeholder="Word trivia, definitions, idioms, etc.\ne.g., A group of crows is called a what?",
        required=True,
        max_length=256,
    )

    correct_answer = TextInput(
        label='Correct Answer',
        style=discord.TextStyle.short,
        placeholder='e.g., Murder',
        required=True,
        max_length=100,
    )

    other_answers = TextInput(
        label='Three Incorrect Answers (separate with comma)',
        style=discord.TextStyle.paragraph,
        placeholder='e.g., Parliament, Conspiracy, Gaggle',
        required=True,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # --- THIS IS THE CORRECTED VALIDATION LOGIC ---

        # 1. Normalize the user's language input (lowercase, no extra spaces)
        user_lang_input = self.language.value.lower().strip()

        # 2. Check if the user's EXACT normalized input is a key in our map.
        # This prevents partial matches like 'englishhhh'.
        if user_lang_input not in self.language_map:
            await interaction.response.send_message(
                f"❌ **Invalid Language:** '{self.language.value}' is not a recognized language. Please use an exact name like `English`, `French`, `Spanish`, etc.",
                ephemeral=True
            )
            return

        # 3. If it's a valid key, get the corresponding locale code.
        locale_code = self.language_map[user_lang_input]

        # The rest of the function remains the same.
        diff_input = self.difficulty.value.lower().strip()
        if diff_input not in self.valid_difficulties:
            await interaction.response.send_message(
                f"❌ **Invalid Difficulty:** Please enter `easy`, `normal`, `hard`, or `insane`.",
                ephemeral=True
            )
            return

        incorrect_answers = [ans.strip() for ans in self.other_answers.value.split(',') if ans.strip()]
        if len(incorrect_answers) != 3:
            await interaction.response.send_message("❌ **Error:** Please provide exactly three incorrect answers.",
                                                    ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ Thank you, {interaction.user.mention}! Your suggestion is submitted.", ephemeral=True)

        embed = discord.Embed(title=f"New Question Suggestion",
                              description=f"**Submitted by:** {interaction.user.mention} (`{interaction.user.id}`)",
                              color=discord.Color.orange())
        embed.add_field(name="Locale", value=f"`{locale_code}`", inline=True)
        embed.add_field(name="Difficulty", value=f"`{diff_input}`", inline=True)
        embed.add_field(name="Question", value=self.question_text.value, inline=False)
        embed.add_field(name="✅ Correct Answer", value=self.correct_answer.value, inline=False)
        embed.add_field(name="❌ Incorrect Answers", value="\n".join(f"- {ans}" for ans in incorrect_answers),
                        inline=False)
        embed.set_footer(text="Awaiting review from a Language Moderator...")
        await self.approval_channel.send(embed=embed, view=ApprovalView())


class QuestionEditModal(Modal, title='Edit Question Suggestion'):
    def __init__(self, data: dict):
        super().__init__()
        self.language = TextInput(label="Language / Locale", default=data.get('language'), required=True, max_length=20)
        self.difficulty = TextInput(label="Difficulty", default=data.get('difficulty'), required=True, max_length=10)
        self.question_text = TextInput(label='Question', default=data.get('question'),
                                       style=discord.TextStyle.paragraph, required=True, max_length=256)
        self.correct_answer = TextInput(label='Correct Answer', default=data.get('correct_answer'), required=True,
                                        max_length=100)
        self.other_answers = TextInput(label='Three Incorrect Answers (comma-separated)',
                                       default=data.get('other_answers'), style=discord.TextStyle.paragraph,
                                       required=True, max_length=300)
        self.add_item(self.language)
        self.add_item(self.difficulty)
        self.add_item(self.question_text)
        self.add_item(self.correct_answer)
        self.add_item(self.other_answers)

    async def on_submit(self, interaction: discord.Interaction):
        # --- THIS IS THE NEW, FLEXIBLE VALIDATION LOGIC ---

        # 1. Define the primary map from name to code
        language_map = {
            "english": "en-US", "portuguese": "pt-BR", "turkish": "tr-TR",
            "french": "fr-FR", "spanish": "es-ES", "tagalog": "tl-TL",
            "german": "de-DE", "italian": "it-IT", "indonesian": "id-ID",
            "swedish": "sv-SE", "russian": "ru", "catalan": "ca-CA",
            "finnish": "fi", "dutch": "nl", "minecraft": "mc-MC"
        }
        # Create a reverse map from code to code for easy lookup
        locale_map = {code.lower(): code for code in language_map.values()}

        valid_difficulties = {"easy", "normal", "hard", "insane"}

        # 2. Normalize the moderator's input
        mod_input = self.language.value.lower().strip()

        locale_code = None
        # 3. First, try to find it as a language name (e.g., "german")
        if mod_input in language_map:
            locale_code = language_map[mod_input]
        # 4. If not found, try to find it as a locale code (e.g., "de-de")
        elif mod_input in locale_map:
            locale_code = locale_map[mod_input]

        # 5. If it's not found in either map, it's invalid.
        if not locale_code:
            return await interaction.response.send_message(
                f"❌ **Invalid Input:** '{self.language.value}' is not a recognized language or locale code.",
                ephemeral=True
            )

        # The rest of the validation and embed creation remains the same
        diff_input = self.difficulty.value.lower().strip()
        if diff_input not in valid_difficulties:
            return await interaction.response.send_message(f"❌ Invalid Difficulty: `{diff_input}`", ephemeral=True)

        incorrect_answers = [ans.strip() for ans in self.other_answers.value.split(',') if ans.strip()]
        if len(incorrect_answers) != 3:
            return await interaction.response.send_message("❌ Error: You must provide exactly three incorrect answers.",
                                                           ephemeral=True)

        original_embed = interaction.message.embeds[0]
        new_embed = discord.Embed(
            title=original_embed.title,
            description=original_embed.description,
            color=original_embed.color
        )

        # Use the validated locale_code for the updated embed
        new_embed.add_field(name="Locale", value=f"`{locale_code}`", inline=True)
        new_embed.add_field(name="Difficulty", value=f"`{diff_input}`", inline=True)
        new_embed.add_field(name="Question", value=self.question_text.value, inline=False)
        new_embed.add_field(name="✅ Correct Answer", value=self.correct_answer.value, inline=False)
        new_embed.add_field(name="❌ Incorrect Answers", value="\n".join(f"- {ans}" for ans in incorrect_answers),
                            inline=False)
        new_embed.set_footer(text=f"Last edited by {interaction.user.display_name}")

        await interaction.response.send_message("✅ Suggestion has been updated!", ephemeral=True)
        await interaction.message.edit(embed=new_embed)

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
                    "you will be credited and it will be added to the new game mode for everyone to enjoy.",
        color=discord.Color.blue()
    )

    # Send the message to the channel with the button view
    await target_channel.send(embed=embed, view=SuggestionStarterView())
    await ctx.send(f"✅ Suggestion button message has been sent to {target_channel.mention}.")


class ApprovalView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # The Approve button logic does NOT need to change
    @ui.button(label='Approve', style=discord.ButtonStyle.green, custom_id='question_approve')
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        # ... (all your existing approve_button code remains here) ...
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
        difficulty_map = {"easy": 0, "normal": 1, "hard": 2, "insane": 3}
        difficulty_int = difficulty_map.get(difficulty_str, 1)
        all_answers = [correct_answer] + incorrect_answers
        right_answer_index = all_answers.index(correct_answer)
        question_document = {
            "q": question, "a": all_answers, "r": right_answer_index,
            "nf": "", "ns": "", "u": submitter_id, "l": locale, "d": difficulty_int
        }
        await questions_collection.insert_one(question_document)
        new_embed = original_embed
        new_embed.color = discord.Color.green()
        new_embed.set_footer(text=f"✅ Approved by {interaction.user.display_name}")
        self.approve_button.disabled = True
        self.decline_button.disabled = True
        self.edit_button.disabled = True  # Also disable the edit button
        await interaction.response.edit_message(embed=new_embed, view=self)

    # --- THIS IS THE NEW BUTTON'S LOGIC ---
    @ui.button(label='Edit', style=discord.ButtonStyle.secondary, custom_id='question_edit')
    async def edit_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id not in LANGUAGE_MOD_IDS and interaction.user.id != 849827666064048178:
            return await interaction.response.send_message("❌ You do not have permission to edit suggestions.",
                                                           ephemeral=True)

        # 1. Parse the data from the current embed on the message
        original_embed = interaction.message.embeds[0]
        try:
            # We need to find the user-friendly language name from the locale code for the form
            language_map = {
                "en-US": "English", "pt-BR": "Portuguese", "tr-TR": "Turkish", "fr-FR": "French",
                "es-ES": "Spanish", "tl-TL": "Tagalog", "de-DE": "German", "it-IT": "Italian",
                "id-ID": "Indonesian", "sv-SE": "Swedish", "ru": "Russian", "ca-CA": "Catalan",
                "fi": "Finnish", "nl": "Dutch", "mc-MC": "Minecraft"
            }
            locale = next(field.value for field in original_embed.fields if field.name == "Locale").strip('`')

            # Find the user-friendly name, or use the code as a fallback
            language_name = next((name for name, code in language_map.items() if code == locale), locale)

            difficulty = next(field.value for field in original_embed.fields if field.name == "Difficulty").strip('`')
            question = next(field.value for field in original_embed.fields if field.name == "Question")
            correct_answer = next(field.value for field in original_embed.fields if field.name == "✅ Correct Answer")

            # Convert the list of incorrect answers back into a comma-separated string for the text field
            incorrect_answers_str = next(
                field.value for field in original_embed.fields if field.name == "❌ Incorrect Answers")
            incorrect_answers_list = [line.lstrip('- ') for line in incorrect_answers_str.split('\n')]
            incorrect_answers_for_modal = ", ".join(incorrect_answers_list)

            # 2. Store the parsed data in a dictionary
            data_to_edit = {
                'language': language_name.capitalize(),
                'difficulty': difficulty,
                'question': question,
                'correct_answer': correct_answer,
                'other_answers': incorrect_answers_for_modal
            }

            # 3. Create and send the pre-populated modal
            await interaction.response.send_modal(QuestionEditModal(data=data_to_edit))

        except (StopIteration, IndexError) as e:
            await interaction.response.send_message(f"Error parsing embed to edit: {e}", ephemeral=True)

    # The Decline button logic also needs to disable the new edit button
    @ui.button(label='Decline', style=discord.ButtonStyle.red, custom_id='question_decline')
    async def decline_button(self, interaction: discord.Interaction, button: ui.Button):
        # ... (your existing decline_button code) ...
        if interaction.user.id not in LANGUAGE_MOD_IDS and interaction.user.id != 849827666064048178:
            await interaction.response.send_message("❌ You do not have permission to decline suggestions.",
                                                    ephemeral=True)
            return
        original_embed = interaction.message.embeds[0]
        if rejected_questions_collection is not None:
            try:
                submitter_id = original_embed.description.split('`')[1]
                question = next(field.value for field in original_embed.fields if field.name == "Question")
                rejected_document = {"q": question, "u": submitter_id, "declined_by": interaction.user.id,
                                     "declined_at": datetime.utcnow()}
                await rejected_questions_collection.insert_one(rejected_document)
            except Exception as e:
                print(f"[ERROR] Failed to save rejected question: {e}")
        new_embed = original_embed
        new_embed.color = discord.Color.red()
        new_embed.set_footer(text=f"❌ Declined by {interaction.user.display_name}")
        self.approve_button.disabled = True
        self.decline_button.disabled = True
        self.edit_button.disabled = True  # Also disable the edit button
        await interaction.response.edit_message(embed=new_embed, view=self)

@bot.command(name="wipe_suggestions_data")
async def wipe_suggestions_data(ctx):
    """A destructive command to permanently delete the old suggestion leaderboard data."""
    # Restrict this command to a developer ID for safety
    DEVELOPER_ID = 849827666064048178  # Using the ID from the `give` command
    if ctx.author.id != DEVELOPER_ID:
        await ctx.send("❌ You do not have permission to use this destructive command.")
        return

    try:
        async with aiosqlite.connect("server_data.db") as db:
            # Drop the tables that stored the old suggestion data
            await db.execute("DROP TABLE IF EXISTS suggest_points")
            await db.execute("DROP TABLE IF EXISTS suggest_pointed_messages")
            await db.commit()

        await ctx.send("✅ Successfully wiped `suggest_points` and `suggest_pointed_messages` tables from the database.")
        print("[ADMIN] Wiped old suggestions data via command.")

    except Exception as e:
        await ctx.send(f"An error occurred while wiping the data: {e}")
        print(f"[ERROR] Failed to wipe suggestions data: {e}")

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
