import discord
from discord import ui
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
import requests
import asyncio

# Load token
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

WORDBOMB_SERVER_TOKEN = os.getenv('WORDBOMB_SERVER_TOKEN')

WORDBOMB_API_BASE = os.getenv("WORDBOMB_API_BASE")
BILL_CREATE_ENDPOINT = os.getenv("WORDBOMB_BILL_CREATE_ENDPOINT")
WALLET_ENDPOINT = os.getenv("WORDBOMB_WALLET_ENDPOINT")

# --- New Constants ---
# Ask Hector for this connection string and put it in your .env file
MONGO_URI = os.getenv('MONGO_URI')
# ID of the private channel where suggestions will be sent for approval
APPROVAL_CHANNEL_ID = 1395207582985097276 # <--- ⚠️ CHANGE THIS TO YOUR LM'S PRIVATE CHANNEL ID


active_coinflips = set()

# --- BLACKJACK CONSTANTS AND STATE ---
SUITS = {"Spades": "♠️", "Hearts": "♥️", "Clubs": "♣️", "Diamonds": "♦️"}
RANKS = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10, "A": 11}

# This dictionary will hold all active games, with the user's ID as the key.
active_blackjack_games = {}

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

# The channel where the "Create Ticket" button will be posted
TICKET_SETUP_CHANNEL_ID = 1395899736032018592
# The category where new ticket channels will be created
TICKET_CATEGORY_ID = 1395901776409923684
# The developer who will be added to all tickets
DEVELOPER_ID = 265196052192165888

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
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS coin_adjustments (
                user_id INTEGER PRIMARY KEY,
                adjustment_amount INTEGER NOT NULL DEFAULT 0
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

    bot.add_view(TicketStarterView())
    bot.add_view(TicketCloseView())

    # 2. Add the new slash command group to the bot's command tree.

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
            if user_id != 265196052192165888:
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


async def _fetch_message_snapshot(channel: discord.TextChannel, reacted_message: discord.Message) -> dict:
    """
    Fetches a snapshot of consecutive messages from the same author,
    returning both the combined text content and the URL of the first image found.
    """
    SEARCH_LIMIT = 25
    TIME_LIMIT_MINUTES = 5
    report_author = reacted_message.author

    snapshot_messages = [reacted_message]

    async for previous_message in channel.history(limit=SEARCH_LIMIT, before=reacted_message):
        if previous_message.author.id != report_author.id:
            break
        time_difference = reacted_message.created_at - previous_message.created_at
        if time_difference.total_seconds() > (TIME_LIMIT_MINUTES * 60):
            break
        snapshot_messages.append(previous_message)

    snapshot_messages.reverse()

    # --- NEW LOGIC: Extract both text and the first image URL ---
    full_conversation = []
    first_image_url = None

    for msg in snapshot_messages:
        # Add the text content if it exists
        if msg.content:
            full_conversation.append(msg.content)

        # If we haven't found an image yet, check for one in this message
        if not first_image_url and msg.attachments:
            for attachment in msg.attachments:
                # Check if the attachment is an image
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    first_image_url = attachment.url
                    break  # Stop after finding the first image

    # Combine the text and format it
    combined_text = "\n".join(full_conversation)
    indented_content = '\n'.join(
        f"> {line}" for line in combined_text.splitlines()) if combined_text else "> (No text content)"

    # Return a dictionary with both pieces of data
    return {"text": indented_content, "image_url": first_image_url}


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
        reacted_message = await channel.fetch_message(payload.message_id)
    except Exception:
        return
    author = reacted_message.author

    # Point-log editing (no changes needed here)
    if payload.channel_id == 1392585590532341782 and str(payload.emoji.name) == "✅":
        if payload.user_id not in DEVELOPER_IDS: return
        try:
            message_to_edit = await channel.fetch_message(payload.message_id)
            lines = message_to_edit.content.splitlines()
            if not lines: return
            first_line, rest_of_message = lines[0], "\n".join(lines[1:])
            mention = message_to_edit.mentions[0].mention if message_to_edit.mentions else "the user"
            if first_line.startswith("🐞"):
                new_first_line = f"🟢 Fixed Bug, reported by {mention}"
            elif first_line.startswith("💡"):
                new_first_line = f"🟢 Implemented Idea by {mention}"
            else:
                new_first_line = "🟢 Handled"
            await message_to_edit.edit(content=f"{new_first_line}\n{rest_of_message}")
        except Exception:
            pass
        return

    # Bug / Idea system
    if payload.user_id not in DEVELOPER_IDS: return
    if payload.emoji.name not in emoji_channel_map: return

    expected_channel_id, pointed_table, points_table, role_name = emoji_channel_map[payload.emoji.name]

    if payload.channel_id != expected_channel_id or author.bot: return

    # Database operations (no changes needed here)
    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute(f"SELECT 1 FROM {pointed_table} WHERE message_id = ?", (payload.message_id,)) as cursor:
            if await cursor.fetchone():
                print(f"[DEBUG] Message {payload.message_id} already gave a point. Skipping.")
                return
        await db.execute(f"INSERT INTO {pointed_table} (message_id) VALUES (?)", (payload.message_id,))
        async with db.execute(f"SELECT count FROM {points_table} WHERE user_id = ?", (author.id,)) as cursor:
            row = await cursor.fetchone()
        new_count = row[0] + 1 if row else 1
        if row:
            await db.execute(f"UPDATE {points_table} SET count = ? WHERE user_id = ?", (new_count, author.id))
        else:
            await db.execute(f"INSERT INTO {points_table} (user_id, count) VALUES (?, ?)", (author.id, 1))
        await db.commit()
    print(f"[DEBUG] {author} now has {new_count} points in {points_table}.")

    # --- THIS IS THE NEW LOGGING LOGIC ---
    # 1. Fetch the snapshot data (which is now a dictionary)
    snapshot_data = await _fetch_message_snapshot(channel, reacted_message)

    if POINT_LOGS_CHANNEL:
        log_title = ""
        log_color = discord.Color.default()
        if payload.emoji.name == BUG_EMOJI:
            log_title = f"🐞 **Bug Reported** by {author.mention}"
            log_color = discord.Color.red()
        elif payload.emoji.name == IDEA_EMOJI:
            log_title = f"💡 **Approved Idea** by {author.mention}"
            log_color = discord.Color.green()

        # 2. Create an embed for the log message
        log_embed = discord.Embed(
            description=f"{snapshot_data['text']}\n\n🔗 [Jump to Message]({reacted_message.jump_url})",
            color=log_color
        )

        # 3. If an image URL was found, add it to the embed
        if snapshot_data['image_url']:
            log_embed.set_image(url=snapshot_data['image_url'])

        # 4. Send the log with the title in the content and the details in the embed
        await POINT_LOGS_CHANNEL.send(content=log_title, embed=log_embed)

    # Handle role assignment (no changes needed here)
    if new_count >= POINT_THRESHOLD:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(author.id)
        if role and member and role not in member.roles:
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

                        if member.id != 265196052192165888:
                            cursor = await db.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (member.id,))
                            row = await cursor.fetchone()
                            if row and row[0] >= 360000:
                                role = discord.utils.get(member.guild.roles, name="Voice Warrior")
                                if role and role not in member.roles:
                                    if member.guild.me.top_role > role and member.guild.me.guild_permissions.manage_roles:
                                        await member.add_roles(role)
                                        print(f"[DEBUG] Gave Voice Warrior role to {member.name}")

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

async def get_coins_leaderboard_data() -> list:
    """
    Gathers all user stats, calculates their effective coin balance, sorts the
    results, and returns them as a list of (user_id, coin_count) tuples.
    """
    from collections import defaultdict
    user_stats = defaultdict(lambda: {
        "messages": 0, "bugs": 0, "ideas": 0,
        "voice_seconds": 0, "trivia": 0, "adjustment": 0
    })

    # --- Step 1: Gather all stats from the databases ---
    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute("SELECT user_id, count FROM messages") as cursor:
            async for user_id, count in cursor:
                user_stats[user_id]["messages"] = count
        async with db.execute("SELECT user_id, count FROM bug_points") as cursor:
            async for user_id, count in cursor:
                user_stats[user_id]["bugs"] = count
        async with db.execute("SELECT user_id, count FROM idea_points") as cursor:
            async for user_id, count in cursor:
                user_stats[user_id]["ideas"] = count
        async with db.execute("SELECT user_id, seconds FROM voice_time") as cursor:
            async for user_id, seconds in cursor:
                user_stats[user_id]["voice_seconds"] = seconds
        async with db.execute("SELECT user_id, adjustment_amount FROM coin_adjustments") as cursor:
            async for user_id, amount in cursor:
                user_stats[user_id]["adjustment"] = amount

    if questions_collection is not None:
        try:
            pipeline = [
                {"$unionWith": {"coll": "rejected"}},
                {"$group": {"_id": "$u", "count": {"$sum": 1}}}
            ]
            cursor = questions_collection.aggregate(pipeline)
            async for doc in cursor:
                try:
                    user_id = int(doc["_id"])
                    user_stats[user_id]["trivia"] = doc["count"]
                except (ValueError, KeyError):
                    continue
        except Exception as e:
            print(f"[ERROR] Could not fetch bulk trivia stats for leaderboard: {e}")

    # --- Step 2: Calculate and compile the final list ---
    leaderboard_entries = []
    for user_id, stats in user_stats.items():
        message_coins = stats["messages"] * 1
        bug_coins = stats["bugs"] * 150
        idea_coins = stats["ideas"] * 100
        voice_coins = int((stats["voice_seconds"] / 3600) * 20)
        trivia_coins = stats["trivia"] * 100
        total_coins = message_coins + bug_coins + idea_coins + voice_coins + trivia_coins + stats["adjustment"]
        if total_coins > 0:
            leaderboard_entries.append((user_id, total_coins))

    # --- Step 3: Sort and return the final data ---
    leaderboard_entries.sort(key=lambda item: item[1], reverse=True)
    return leaderboard_entries

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

    @discord.ui.button(label="Coins", style=discord.ButtonStyle.primary, custom_id="category_coins")
    async def coins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "coins", 1, self.author_id)

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
    table_map = {
        "messages": "messages",
        "bugs": "bug_points",
        "ideas": "idea_points",
        "voice": "voice_time"
    }
    label_map = {
        "trivia": ("question suggested", "questions suggested"),
        "messages": ("message", "messages"),
        "bugs": ("bug found", "bugs found"),
        "ideas": ("idea", "ideas"),
        "voice": ("second", "seconds"),
        "coins": ("coin", "coins")
    }

    full_rows = []

    if category == "coins":
        full_rows = await get_coins_leaderboard_data()
    elif category == "trivia":
        if questions_collection is not None and rejected_questions_collection is not None:
            pipeline = [
                {"$unionWith": {"coll": "rejected"}},
                {"$group": {"_id": "$u", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
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
        # This part for SQLite leaderboards remains the same.
        if category not in table_map:
            # This check will now only apply to categories that are supposed to be in table_map.
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

        banned_role_name = "Suggestion Limited"
        if any(role.name == banned_role_name for role in interaction.user.roles):
            await interaction.response.send_message(
                "🚫 You are limited from submitting suggestions.",
                ephemeral=True
            )

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


# --- TICKETS ---

# This view is for the final "Confirm" or "Cancel" action. It's not persistent.
class TicketConfirmCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)  # This view only lasts for 60 seconds

    @ui.button(label='Confirm Close', style=discord.ButtonStyle.danger, custom_id='ticket_confirm_close')
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Closing the ticket...", ephemeral=True)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user.name}")

    @ui.button(label='Cancel', style=discord.ButtonStyle.secondary, custom_id='ticket_cancel_close')
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        # Just delete the confirmation message
        await interaction.message.delete()


# This persistent view contains the "Close Ticket" button inside a ticket channel.
class TicketCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, custom_id='close_ticket_button')
    async def close_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        # --- THIS IS THE ONLY CHANGE ---
        # The check for the creator_id has been removed.
        # Now, only the developer can initiate the closing process.
        if interaction.user.id != DEVELOPER_ID and interaction.user.id != 849827666064048178:
            return await interaction.response.send_message(
                "Only the developer can close this ticket.",
                ephemeral=True
            )

        # The rest of the function (sending the confirmation) remains the same.
        await interaction.response.send_message(
            "Are you sure you want to close this ticket? This action cannot be undone.",
            view=TicketConfirmCloseView(),
            ephemeral=True
        )


# This persistent view contains the initial "Create Ticket" button.
class TicketStarterView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Create Ticket', style=discord.ButtonStyle.green, custom_id='create_ticket_button')
    async def create_ticket_button(self, interaction: discord.Interaction, button: ui.Button):

        banned_role_name = "Ticket Limited"
        if any(role.name == banned_role_name for role in interaction.user.roles):
            await interaction.response.send_message(
                "🚫 You are limited from creating tickets.",
                ephemeral=True
            )

        await interaction.response.send_message("Creating your private ticket channel...", ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        # Fetch the category where tickets will be created
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.followup.send("Error: Ticket category not found. Please contact an admin.",
                                            ephemeral=True)
            return

        # Fetch the developer member object
        developer = guild.get_member(DEVELOPER_ID)
        if not developer:
            await interaction.followup.send("Error: Developer user not found in this server.", ephemeral=True)
            return

        # Check if the user already has an open ticket channel
        ticket_channel_name = f"ticket-{user.name}-{user.discriminator}"
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_channel_name, category=category)
        if existing_channel:
            await interaction.followup.send(f"You already have an open ticket: {existing_channel.mention}",
                                            ephemeral=True)
            return

        # Define permissions for the new channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True,
                                              embed_links=True),
            developer: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True,
                                                   embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Ensure the bot can see it
        }

        # Create the new private channel
        try:
            new_channel = await guild.create_text_channel(
                name=ticket_channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket created by: {user.id}"  # Store the user ID for permission checks later
            )
        except discord.Forbidden:
            return await interaction.followup.send("I don't have permission to create channels.", ephemeral=True)
        except Exception as e:
            return await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)

        # Send a welcome message in the new channel
        welcome_embed = discord.Embed(
            title=f"Ticket for {user.display_name}",
            description="Thank you for creating a ticket. Please describe your issue in detail, and be patient for a response.",
            color=discord.Color.blue()
        )

        # Ping the user and the developer
        await new_channel.send(
            content=f"Welcome, {user.mention}! {developer.mention} has been notified.",
            embed=welcome_embed,
            view=TicketCloseView()  # Add the "Close Ticket" button
        )

        await interaction.followup.send(f"Your ticket has been created: {new_channel.mention}", ephemeral=True)


async def calculate_total_coins_from_stats(user_id: int) -> int:
    """
    Calculates a user's total coin balance by converting all their historical stats.
    """
    total_coins = 0

    # 1. Calculate from SQLite stats (Messages, Bugs, Ideas, Voice)
    async with aiosqlite.connect("server_data.db") as db:
        # Messages: 1 coin per message
        msg_cursor = await db.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,))
        if msg_row := await msg_cursor.fetchone():
            total_coins += msg_row[0] * 1

        # Bug Reports: 150 coins per report
        bug_cursor = await db.execute("SELECT count FROM bug_points WHERE user_id = ?", (user_id,))
        if bug_row := await bug_cursor.fetchone():
            total_coins += bug_row[0] * 150

        # Ideas: 100 coins per idea
        idea_cursor = await db.execute("SELECT count FROM idea_points WHERE user_id = ?", (user_id,))
        if idea_row := await idea_cursor.fetchone():
            total_coins += idea_row[0] * 100

        # Voice Time: 20 coins per hour
        voice_cursor = await db.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (user_id,))
        if voice_row := await voice_cursor.fetchone():
            hours = voice_row[0] / 3600
            total_coins += int(hours * 20)

    # 2. Calculate from MongoDB stats (Trivia Questions)
    # --- THIS IS THE CORRECTED LINE ---
    if questions_collection is not None:
        pipeline = [
            {"$unionWith": {"coll": "rejected"}},
            {"$match": {"u": str(user_id)}},
            {"$count": "total_suggestions"}
        ]
        try:
            result = await questions_collection.aggregate(pipeline).to_list(length=1)
            if result:
                suggestion_count = result[0]['total_suggestions']
                total_coins += suggestion_count * 100
        except Exception as e:
            print(f"[ERROR] Could not fetch trivia stats for {user_id}: {e}")

    return total_coins

async def get_coin_adjustment(user_id: int) -> int:
    """Fetches the current win/loss adjustment for a user from the database."""
    async with aiosqlite.connect("server_data.db") as db:
        await db.execute("INSERT OR IGNORE INTO coin_adjustments (user_id, adjustment_amount) VALUES (?, 0)",
                         (user_id,))
        cursor = await db.execute("SELECT adjustment_amount FROM coin_adjustments WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def modify_coin_adjustment(user_id: int, amount_change: int) -> bool:
    """Modifies the user's gambling adjustment by a certain amount (positive for win, negative for loss)."""
    try:
        async with aiosqlite.connect("server_data.db") as db:
            await db.execute("INSERT OR IGNORE INTO coin_adjustments (user_id, adjustment_amount) VALUES (?, 0)",
                             (user_id,))
            await db.execute("UPDATE coin_adjustments SET adjustment_amount = adjustment_amount + ? WHERE user_id = ?",
                             (amount_change, user_id))
            await db.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to modify coin adjustment for {user_id}: {e}")
        return False


async def get_effective_balance(user_id: int) -> int:
    """
    The main function to get a user's final, playable coin balance.
    This is the sum of their stat-based coins and their gambling adjustments.
    """
    stats_balance = await calculate_total_coins_from_stats(user_id)
    adjustment = await get_coin_adjustment(user_id)
    return stats_balance + adjustment

# Coinflip
@bot.command(name="cf", aliases=["coinflip"])
async def coinflip(ctx: commands.Context, amount: int):
    """Gamble your coins based on your total leaderboard stats."""
    author = ctx.author

    if author.id in active_coinflips:
        return await ctx.send("You already have a coinflip in progress! Please wait for it to finish.", ephemeral=True)

    if amount <= 0:
        await ctx.send("Please enter a positive amount of coins to bet.", ephemeral=True)
        return

    # Get the user's total effective balance
    current_balance = await get_effective_balance(author.id)
    if current_balance < amount:
        return await ctx.send(f"You don't have enough coins! You only have **{current_balance:,}** 🪙.", ephemeral=True)

    active_coinflips.add(author.id)
    try:
        flipping_embed = discord.Embed(title=f"{author.display_name}'s Coinflip...",
                                       color=discord.Color.blue()).set_image(
            url="https://discord.wordbomb.io/coin_flip.gif?v=2")
        result_message = await ctx.send(embed=flipping_embed)
        await asyncio.sleep(3.0)

        win_chance = 50
        won = random.randint(1, 100) <= win_chance

        # Determine the net change and update the adjustment
        net_change = amount if won else -amount
        success = await modify_coin_adjustment(author.id, net_change)

        if not success:
            error_embed = discord.Embed(title="Database Error",
                                        description="An error occurred saving the result. Please try again.",
                                        color=discord.Color.orange())
            await result_message.edit(embed=error_embed)
            return

        # Calculate the new final balance for display
        new_balance = current_balance + net_change

        result_image_url = "https://discord.wordbomb.io/coin_win.png?v=2" if won else "https://discord.wordbomb.io/coin_lost.png?v=2"
        final_embed = discord.Embed(title="The coin has landed!",
                                    color=discord.Color.green() if won else discord.Color.red()).set_image(
            url=result_image_url)
        await result_message.edit(embed=final_embed)
        await asyncio.sleep(1)

        final_embed.title = "🎉 You Won! 🎉" if won else "😭 You Lost! 😭"
        final_embed.description = f"You won **{amount:,}** 🪙!" if won else f"You lost **{amount:,}** 🪙."
        final_embed.set_author(name=f"{author.display_name}'s Coinflip", icon_url=author.display_avatar.url)
        final_embed.add_field(name="Your Bet", value=f"{amount:,} 🪙")
        final_embed.add_field(name="New Balance", value=f"{new_balance:,} 🪙")
        await result_message.edit(embed=final_embed)

    finally:
        active_coinflips.remove(author.id)

def create_deck():
    """Creates a standard 52-card deck and shuffles it."""
    deck = [(suit, rank) for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def calculate_hand_value(hand):
    """Calculates the value of a hand, correctly handling the value of Aces."""
    value = 0
    num_aces = 0
    for _, rank in hand:
        value += RANKS[rank]
        if rank == 'A':
            num_aces += 1

    # If the total value is over 21, convert Aces from 11 to 1 until the value is 21 or less.
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1

    return value


def hand_to_string(hand, hide_dealer_card=False):
    """Converts a list of cards into a visually appealing string."""
    if hide_dealer_card:
        # Shows the back of the first card and the face of the second
        return f"`[?]` ` {SUITS[hand[1][0]]} {hand[1][1]} `"

    # Joins all cards in hand into a single string
    return " ".join([f"` {SUITS[card[0]]} {card[1]} `" for card in hand])


async def end_blackjack_game(interaction: discord.Interaction, result: str):
    """
    Finalizes the game, displays the final hands, calculates winnings,
    updates the coin adjustment, and edits the final message.
    """
    user_id = interaction.user.id
    if user_id not in active_blackjack_games:
        return  # Game already ended

    game = active_blackjack_games[user_id]
    bet = game['bet']

    # --- THIS IS THE NEW, CRUCIAL LOGIC ---
    # Calculate final values and display both hands fully revealed.
    # This ensures the user always sees the final state.
    player_value = calculate_hand_value(game['player_hand'])
    dealer_value = calculate_hand_value(game['dealer_hand'])

    final_embed = interaction.message.embeds[0]
    final_embed.clear_fields()  # Remove old fields for a clean final state

    final_embed.add_field(name=f"Dealer's Hand ({dealer_value})", value=hand_to_string(game['dealer_hand']), inline=False)
    final_embed.add_field(name=f"Your Hand ({player_value})", value=hand_to_string(game['player_hand']), inline=False)
    # --- END OF NEW LOGIC ---

    net_change = -bet  # Start with the initial bet loss

    if result == 'blackjack':
        net_change += bet + int(bet * 1.5)  # Win bet back + 1.5x winnings
        final_embed.title = "🎉 BLACKJACK! 🎉"
        final_embed.color = discord.Color.gold()
        final_embed.description = f"A natural 21 pays 3:2! You won **{int(bet * 1.5):,}** 🪙!"
    elif result == 'win':
        net_change += bet * 2  # Win bet back + winnings
        final_embed.title = "✅ You Win! ✅"
        final_embed.color = discord.Color.green()
        final_embed.description = f"You won **{bet:,}** 🪙!"
    elif result == 'push':
        net_change += bet  # Get the bet back
        final_embed.title = "➖ Push ➖"
        final_embed.color = discord.Color.light_grey()
        final_embed.description = "It's a tie! Your bet has been returned."
    elif result == 'bust':
        # net_change is already -bet
        final_embed.title = "❌ Bust! ❌"
        final_embed.color = discord.Color.dark_red()
        final_embed.description = f"You went over 21 and lost your bet of **{bet:,}** 🪙."
    else:  # 'loss' or 'timeout'
        # net_change is already -bet
        final_embed.title = "Game Timed Out" if result == 'timeout' else "You Lose"
        final_embed.color = discord.Color.dark_grey() if result == 'timeout' else discord.Color.red()
        final_embed.description = f"You lost your bet of **{bet:,}** 🪙."

    # Apply the single adjustment
    success = await modify_coin_adjustment(user_id, net_change)
    if not success:
        await modify_coin_adjustment(user_id, bet)
        final_embed.description = "A database error occurred. Your original bet has been refunded."

    del active_blackjack_games[user_id]
    await interaction.message.edit(embed=final_embed, view=None)

# --- BLACKJACK INTERACTIVE VIEW ---

class BlackjackView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120.0)  # Game times out after 2 minutes of inactivity
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures that only the user who started the game can use the buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        """Handles the game when the user is AFK."""
        if self.author_id in active_blackjack_games:
            game = active_blackjack_games[self.author_id]
            channel = bot.get_channel(game['channel_id'])
            if channel:
                try:
                    # We create a lightweight object that mimics an interaction
                    # so we can reuse our end_game function.
                    class DummyInteraction:
                        def __init__(self, user, message):
                            self.user = user
                            self.message = message

                    message = await channel.fetch_message(game['message_id'])
                    user = bot.get_user(self.author_id)
                    dummy_interaction = DummyInteraction(user, message)

                    await end_blackjack_game(dummy_interaction, 'timeout')
                except discord.NotFound:
                    # Message was deleted, just clean up state
                    del active_blackjack_games[self.author_id]

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, custom_id="bj_hit")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Gives the player another card."""
        game = active_blackjack_games[self.author_id]
        game['player_hand'].append(game['deck'].pop())
        player_value = calculate_hand_value(game['player_hand'])

        if player_value > 21:
            await end_blackjack_game(interaction, 'bust')
        else:
            embed = interaction.message.embeds[0]
            embed.set_field_at(1, name=f"Your Hand ({player_value})", value=hand_to_string(game['player_hand']),
                               inline=False)

            # If player hits 21, their turn is automatically over.
            if player_value == 21:
                button.disabled = True
                self.children[1].disabled = True  # Disable stand button
                await interaction.response.edit_message(embed=embed, view=self)
                await self.dealer_turn(interaction)
            else:
                await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger, custom_id="bj_stand")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Ends the player's turn and starts the dealer's turn."""
        button.disabled = True
        self.children[0].disabled = True  # Disable hit button
        await interaction.response.edit_message(view=self)
        await self.dealer_turn(interaction)

    async def dealer_turn(self, interaction: discord.Interaction):
        """Reveals the dealer's hand and plays out their turn according to standard rules."""
        game = active_blackjack_games[self.author_id]
        embed = interaction.message.embeds[0]

        # Reveal dealer's hidden card and update hand value
        dealer_value = calculate_hand_value(game['dealer_hand'])
        embed.set_field_at(0, name=f"Dealer's Hand ({dealer_value})", value=hand_to_string(game['dealer_hand']),
                           inline=False)
        await interaction.message.edit(embed=embed)

        # Dealer must hit until their hand value is 17 or higher
        while calculate_hand_value(game['dealer_hand']) < 17:
            game['dealer_hand'].append(game['deck'].pop())
            dealer_value = calculate_hand_value(game['dealer_hand'])
            embed.set_field_at(0, name=f"Dealer's Hand ({dealer_value})", value=hand_to_string(game['dealer_hand']),
                               inline=False)
            await interaction.message.edit(embed=embed)

        # Determine the winner
        player_value = calculate_hand_value(game['player_hand'])
        dealer_value = calculate_hand_value(game['dealer_hand'])

        if dealer_value > 21:
            await end_blackjack_game(interaction, 'win')  # Dealer busts
        elif dealer_value > player_value:
            await end_blackjack_game(interaction, 'loss')
        elif player_value > dealer_value:
            await end_blackjack_game(interaction, 'win')
        else:
            await end_blackjack_game(interaction, 'push')


# --- BLACKJACK COMMAND ---

@bot.command(name="bj", aliases=["blackjack"])
async def blackjack(ctx: commands.Context, amount: int):
    author = ctx.author
    if author.id in active_blackjack_games:
        return await ctx.send("You're already in a game!", ephemeral=True)
    if amount <= 0:
        return await ctx.send("You must bet a positive amount.", ephemeral=True)

    # Get the user's total effective balance
    current_balance = await get_effective_balance(author.id)
    if current_balance < amount:
        return await ctx.send(f"You don't have enough coins! You have **{current_balance:,}** 🪙.", ephemeral=True)

    # --- The rest of the game setup logic remains the same ---
    # (create deck, deal cards, create embed, send message, check for natural blackjack)
    deck = create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    player_value = calculate_hand_value(player_hand)
    embed = discord.Embed(title=f"{author.display_name}'s Blackjack Game", color=0x2E3136)
    embed.add_field(name="Dealer's Hand (?)", value=hand_to_string(dealer_hand, hide_dealer_card=True), inline=False)
    embed.add_field(name=f"Your Hand ({player_value})", value=hand_to_string(player_hand), inline=False)
    embed.set_footer(text=f"Your Bet: {amount:,} coins")
    view = BlackjackView(author.id)
    game_message = await ctx.send(embed=embed, view=view)
    active_blackjack_games[author.id] = { "deck": deck, "player_hand": player_hand, "dealer_hand": dealer_hand, "bet": amount, "message_id": game_message.id, "channel_id": ctx.channel.id }

    # Check for immediate Blackjack
    if player_value == 21:
        view.stop()
        class DummyInteraction:
            def __init__(self, user, message): self.user, self.message = user, message
        dummy_interaction = DummyInteraction(author, game_message)
        result = 'blackjack' if calculate_hand_value(dealer_hand) != 21 else 'push'
        await end_blackjack_game(dummy_interaction, result)

# --- ADD THIS NEW ADMIN COMMAND ---

@bot.command(name="setup_tickets")
async def setup_tickets(ctx):
    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this command.")
    """Sends the persistent message with the 'Create Ticket' button."""
    target_channel = bot.get_channel(TICKET_SETUP_CHANNEL_ID)
    if not target_channel:
        return await ctx.send("Error: Ticket setup channel not found.")

    embed = discord.Embed(
        title="Create a Private Ticket",
        description="Click the button below to create a private channel to discuss your issue directly with the developer.",
        color=discord.Color.green()
    ).set_footer(text="Use this for sensitive reports regarding moderators, cheaters, or issues in general.")

    await target_channel.send(embed=embed, view=TicketStarterView())

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
