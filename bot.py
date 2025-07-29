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
import asyncio
import math

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

# --- ROULETTE GAME CONSTANTS AND STATE ---

# Represents the 38 pockets of an American Roulette wheel
ROULETTE_POCKETS = {
    0: "green", 1: "red", 2: "black", 3: "red", 4: "black", 5: "red",
    6: "black", 7: "red", 8: "black", 9: "red", 10: "black", 11: "black",
    12: "red", 13: "black", 14: "red", 15: "black", 16: "red", 17: "black",
    18: "red", 19: "red", 20: "black", 21: "red", 22: "black", 23: "red",
    24: "black", 25: "red", 26: "black", 27: "red", 28: "black", 29: "black",
    30: "red", 31: "black", 32: "red", 33: "black", 34: "red", 35: "black",
    36: "red", "00": "green"
}
# Define columns and dozens for betting
COLUMN_1 = {1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34}
COLUMN_2 = {2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35}
COLUMN_3 = {3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36}
DOZEN_1 = set(range(1, 13))
DOZEN_2 = set(range(13, 25))
DOZEN_3 = set(range(25, 37))

# This dictionary will hold all active games, with the user's ID as the key.
active_blackjack_tables = {}
active_baccarat_games = {}
active_duels = {}
active_roulette_games = {}

BLACKJACK_CATEGORY_ID = 1399582975146065941 # <-- PASTE YOUR CATEGORY ID HERE
# The logical table slots that players can choose from.
LOGICAL_TABLES = {
    "Table 1": {"name": "🃏-table-one"},
    "Table 2": {"name": "🃏-table-two"},
    "High Roller": {"name": "🃏-high-roller"}
}

MAX_PLAYERS_PER_TABLE = 5 # This logic can be handled differently or kept if you wish
SHOE_RESHUFFLE_THRESHOLD = 0.25 # This is fine to keep

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
                  "/wordle - Get Wordle results for a user",
                  "!i - Get information about a word"],
    "Word Bomb Tracker": ["!leaderboards - Get information on the leaderboard",
                          "!give - Give a user <:wbcoin:1398780929664745652>",
                          "!bj `<amount>` - Play blackjack to earn <:wbcoin:1398780929664745652>!",
                          "!cf `<amount>` - Do a coinflip and test your luck to earn <:wbcoin:1398780929664745652>!",
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
        message_coins = stats["messages"] * 75
        bug_coins = stats["bugs"] * 50000
        idea_coins = stats["ideas"] * 40000
        voice_coins = int((stats["voice_seconds"] / 3600) * 5000)
        trivia_coins = stats["trivia"] * 20000
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
        display_count = f"{count // 3600}h {(count % 3600) // 60}m {count % 60}s" if category == "voice" else f"{count:,} {unit}"
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

    if category == "coins":
        # If the category is "coins", use your custom emoji string.
        embed_title = f"<:wbcoin:1398780929664745652> Leaderboard"
    else:
        # Otherwise, use the default title format.
        embed_title = f"🏆 {category.capitalize()} Leaderboard"

    embed = discord.Embed(title=embed_title, description=description,
                          color=discord.Color.gold())

    rate_map = {
        "messages": "Each message gives 75 coins.",
        "bugs": "Each approved bug report gives 50,000 coins.",
        "ideas": "Each approved idea gives 40,000 coins.",
        "voice": "Voice activity is worth 5,000 coins per hour.",
        "trivia": "Each approved trivia question gives 20,000 coins.",
        "coins": "The total of all coins earned from server activity."  # Footer for the main coins page
    }

    # Get the correct footer text for the current category.
    footer_text = rate_map.get(category, "")  # Safely gets the text, returns empty if not found

    # Only add the footer if we found text for it.
    if footer_text:
        embed.set_footer(text=footer_text)

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


@bot.command(name="give", aliases=["pay", "transfer"])
async def give(ctx: commands.Context, arg1: str, arg2: str):
    """
    Allows a player to give coins to another player.
    The order of the user and amount does not matter.
    Example: !give @User 500  OR  !give 500 @User
    """
    giver = ctx.author

    # --- 1. NEW, MORE ROBUST PARSING LOGIC ---
    receiver = None
    amount = None
    member_converter = commands.MemberConverter()

    # Try to parse the arguments as (amount, user)
    try:
        amount = int(arg1)
        receiver = await member_converter.convert(ctx, arg2)
    except (ValueError, commands.BadArgument):
        # If that fails, try parsing them as (user, amount)
        try:
            receiver = await member_converter.convert(ctx, arg1)
            amount = int(arg2)
        except (ValueError, commands.BadArgument):
            # If both ways fail, the input is invalid
            pass

    # --- 2. VALIDATION OF PARSED ARGUMENTS ---
    if receiver is None or amount is None:
        await ctx.send(
            "❌ Incorrect usage. You must specify a valid user and a whole number amount.\n"
            "**Examples:**\n`!give @User 500`\n`!give 500 @User`"
        )
        return

    # --- 3. ORIGINAL VALIDATION LOGIC ---
    if giver.id == receiver.id:
        await ctx.send("❌ You cannot give coins to yourself!")
        return
    if receiver.bot:
        await ctx.send("❌ You cannot give coins to a bot. They have no use for them!")
        return
    if amount <= 0:
        await ctx.send("❌ You must give a positive amount of coins.")
        return

    # --- 4. BALANCE CHECK ---
    giver_balance = await get_effective_balance(giver.id)
    if giver_balance < amount:
        await ctx.send(
            f"❌ You don't have enough coins! You only have **{giver_balance:,}** <:wbcoin:1398780929664745652>."
        )
        return

    # --- 5. THE TRANSACTION ---
    try:
        await modify_coin_adjustment(giver.id, -amount)
        await modify_coin_adjustment(receiver.id, amount)
    except Exception as e:
        await ctx.send("❌ An unexpected error occurred while processing the transaction.")
        print(f"[ERROR] An exception occurred during the give command: {e}")
        # Attempt to refund the giver if the transaction failed partway
        await modify_coin_adjustment(giver.id, amount)
        return

    # --- 6. FETCH NEW BALANCES AND SEND CONFIRMATION ---
    new_giver_balance = await get_effective_balance(giver.id)
    new_receiver_balance = await get_effective_balance(receiver.id)

    embed = discord.Embed(
        title="✅ Transaction Successful!",
        description=f"{giver.mention} has successfully given **{amount:,}** <:wbcoin:1398780929664745652> to {receiver.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(name=f"{giver.display_name}'s New Balance",
                    value=f"{new_giver_balance:,} <:wbcoin:1398780929664745652>", inline=True)
    embed.add_field(name=f"{receiver.display_name}'s New Balance",
                    value=f"{new_receiver_balance:,} <:wbcoin:1398780929664745652>", inline=True)
    embed.set_footer(text=f"Requested by {giver.display_name}")
    await ctx.send(embed=embed)


@give.error
async def give_error(ctx, error):
    """Handles specific errors for the give command."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Incorrect usage. You must specify a user and an amount.\n"
            "**Examples:**\n`!give @User 500`\n`!give 500 @User`"
        )

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
    Calculates a user's total coin balance by converting all their historical stats
    using the NEW proportions.
    """
    total_coins = 0

    # 1. Calculate from SQLite stats (Messages, Bugs, Ideas, Voice)
    async with aiosqlite.connect("server_data.db") as db:
        # Messages: 75 coins per message
        msg_cursor = await db.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,))
        if msg_row := await msg_cursor.fetchone():
            total_coins += msg_row[0] * 75

        # Bug Reports: 50,000 coins per report
        bug_cursor = await db.execute("SELECT count FROM bug_points WHERE user_id = ?", (user_id,))
        if bug_row := await bug_cursor.fetchone():
            total_coins += bug_row[0] * 50000

        # Ideas: 40,000 coins per idea
        idea_cursor = await db.execute("SELECT count FROM idea_points WHERE user_id = ?", (user_id,))
        if idea_row := await idea_cursor.fetchone():
            total_coins += idea_row[0] * 40000

        # Voice Time: 5,000 coins per hour
        voice_cursor = await db.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (user_id,))
        if voice_row := await voice_cursor.fetchone():
            hours = voice_row[0] / 3600
            total_coins += int(hours * 5000)

    # 2. Calculate from MongoDB stats (Trivia Questions)
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
                # Trivia: 20,000 coins per suggestion
                total_coins += suggestion_count * 20000
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
    MAX_VALUE = 100000

    if author.id in active_coinflips:
        return await ctx.send("You already have a coinflip in progress! Please wait for it to finish.", ephemeral=True)

    if amount <= 0:
        await ctx.send("Please enter a positive amount of coins to bet.", ephemeral=True)
        return
    if amount > MAX_VALUE:
        await ctx.send("Maximum betting is 100,000 <:wbcoin:1398780929664745652>!", ephemeral=True)
        return

    # Get the user's total effective balance
    current_balance = await get_effective_balance(author.id)
    if current_balance < amount:
        return await ctx.send(f"You don't have enough coins! You only have **{current_balance:,}** <:wbcoin:1398780929664745652>.", ephemeral=True)

    # Lock the user at the very beginning
    active_coinflips.add(author.id)

    try:

        # --- All critical calculations happen BEFORE the unlock ---
        win_chance = 50
        won = random.randint(1, 100) <= win_chance
        net_change = amount if won else -amount
        success = await modify_coin_adjustment(author.id, net_change)
        # --- Database is now safely updated ---

        if won:
            animation_duration = 3.0
            final_image_url = "https://discord.wordbomb.io/coin_win.png?v=2"
        else:
            animation_duration = 3.17
            final_image_url = "https://discord.wordbomb.io/coin_lost.png?v=2"

        flipping_embed = discord.Embed(title=f"{author.display_name}'s Coinflip...",
                                       color=discord.Color.blue()).set_image(
            url="https://discord.wordbomb.io/coin_flip.gif?v=2")
        result_message = await ctx.send(embed=flipping_embed)

        # The 3-second animation plays
        await asyncio.sleep(animation_duration)

        if not success:
            error_embed = discord.Embed(title="Database Error",
                                        description="An error occurred saving the result. Please try again.",
                                        color=discord.Color.orange())
            await result_message.edit(embed=error_embed)
            # Make sure to unlock the user even if there's an error
            active_coinflips.remove(author.id)
            return

        # Calculate the new final balance for display
        new_balance = current_balance + net_change

        # Edit the message to the static win/loss image
        final_embed = discord.Embed(title="The coin has landed!",
                                    color=discord.Color.green() if won else discord.Color.red()).set_image(
            url=final_image_url)
        await result_message.edit(embed=final_embed)

        active_coinflips.remove(author.id)

        await asyncio.sleep(1)

        final_embed.title = "🎉 You Won! 🎉" if won else "😭 You Lost! 😭"
        final_embed.description = f"You won **{amount:,}** <:wbcoin:1398780929664745652>!" if won else f"You lost **{amount:,}** <:wbcoin:1398780929664745652>."
        final_embed.set_author(name=f"{author.display_name}'s Coinflip", icon_url=author.display_avatar.url)
        final_embed.add_field(name="Your Bet", value=f"{amount:,} <:wbcoin:1398780929664745652>")
        final_embed.add_field(name="New Balance", value=f"{new_balance:,} <:wbcoin:1398780929664745652>")
        await result_message.edit(embed=final_embed)

    except Exception as e:
        # Generic error handler to ensure the user is always unlocked
        print(f"[ERROR] An unexpected error occurred in coinflip: {e}")
        if author.id in active_coinflips:
            active_coinflips.remove(author.id)

# Blackjack

def create_shoe(num_decks=2):
    """Creates a multi-deck shoe and shuffles it."""
    shoe = []
    for _ in range(num_decks):
        for suit in SUITS:
            for rank in RANKS:
                shoe.append((suit, rank))
    random.shuffle(shoe)
    return shoe


def calculate_hand_value(hand):
    """Calculates the value of a hand, correctly handling Aces."""
    value, num_aces = 0, 0
    for _, rank in hand:
        value += RANKS[rank]
        if rank == 'A':
            num_aces += 1
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
    return value


def hand_to_string(hand, is_dealer=False, hide_card=False):
    """Converts a list of cards into a visually appealing string."""
    if is_dealer and hide_card:
        return f"`{SUITS[hand[0][0]]} {hand[0][1]}` `[?]`"
    return " ".join([f"`{SUITS[card[0]]} {card[1]}`" for card in hand])


class BettingView(ui.View): pass


class PlayerActionView(ui.View): pass


# This function is now defined first as it's called by almost every other function.
async def _update_game_embed(logical_name: str, results_log: list = None):
    """The single source of truth for updating the game's visual state."""
    table = active_blackjack_tables.get(logical_name)
    if not table: return

    # If the message reference is lost, try to recover by re-initializing.
    # if not table.get("game_message"):
    #     print(f"[BJ RECOVERY] Table state for {logical_name} has no message. Re-initializing.")
    #     await _initialize_table(logical_name)
    #     return

    game_message = table["game_message"]
    embed = discord.Embed(title=f"🎲 {logical_name} 🎲", color=0x2E3136)
    view = None

    player_lines = []
    for p_id, p_data in table.get("players", {}).items():
        member = p_data.get("member")
        if not member: continue
        status_emoji = {"betting": "💰", "playing": "🤔", "stood": "✅", "busted": "❌", "blackjack": "🎉"}.get(
            p_data.get("status"), "")
        bet_str = f"Bet: `{p_data.get('bet', 0):,}`" if p_data.get('bet', 0) > 0 else ""
        hand = p_data.get('hand', [])
        hand_value = calculate_hand_value(hand)
        hand_str = f"({hand_value}) {hand_to_string(hand)}" if hand else ""
        turn_indicator = "▶️ " if table.get("current_player_id") == p_id else ""
        player_lines.append(f"{turn_indicator}{status_emoji} **{member.display_name}** {bet_str} {hand_str}")

    if table.get("waiting_to_join"):
        waiting_names = ", ".join([m.display_name for m in table["waiting_to_join"]])
        player_lines.append(f"\n*Waiting for next hand: {waiting_names}*")

    embed.add_field(name="Players", value="\n".join(player_lines) if player_lines else "No players seated.",
                    inline=False)

    dealer_hand = table.get("dealer_hand", [])
    if dealer_hand:
        hide_card = table.get("status") == "player_turns"
        dealer_value = calculate_hand_value(dealer_hand) if not hide_card else RANKS.get(dealer_hand[0][1], 0)
        embed.add_field(name=f"Dealer's Hand ({dealer_value if not hide_card else '?'})",
                        value=hand_to_string(dealer_hand, is_dealer=True, hide_card=hide_card), inline=False)

    shoe_size = len(create_shoe(2))
    embed.set_footer(text=f"Shoe Status: {len(table.get('shoe', []))} / {shoe_size} cards remaining.")

    game_status = table.get("status")
    if game_status == "waiting_for_bets" or game_status == "waiting_for_players":
        embed.description = "The table is open for betting. Place your bets to be included in the next hand!"
        view = BettingView(logical_name)  # Pass logical_name
    elif game_status == "player_turns":
        current_player_id = table.get('current_player_id')
        current_player = table.get("players", {}).get(current_player_id)
        if current_player and current_player.get("member"):
            embed.description = f"It is **{current_player.get('member').display_name}**'s turn to act."
            player_balance = await get_effective_balance(current_player_id)
            can_double = player_balance >= current_player.get('bet', 0) and len(current_player.get('hand', [])) == 2
            view = PlayerActionView(logical_name, can_double=can_double) # Pass logical_name
    elif game_status == "dealer_turn":
        embed.description = "All players have acted. The dealer will now play their hand."
    elif game_status == "hand_over":
        embed.description = "**Hand Results:**\n" + "\n".join(results_log if results_log else ["Hand concluded."])

    try:
        await game_message.edit(embed=embed, view=view)
    except discord.NotFound:
        print(f"[BJ RECOVERY] Game message for {logical_name} was deleted. Re-initializing table.")
        await _initialize_table(logical_name)
    except Exception as e:
        print(f"[BJ ERROR] Failed to edit game message for table {logical_name}: {e}")


async def _resolve_hand(channel_id: int):
    """Compares all hands to the dealer's, processes payouts, and ends the hand."""
    table = active_blackjack_tables.get(channel_id)
    if not table: return

    table["status"] = "hand_over"
    dealer_value = calculate_hand_value(table["dealer_hand"])
    dealer_busted = dealer_value > 21

    results_log = []

    for p_id, p_data in list(table["players"].items()):
        player_value = calculate_hand_value(p_data["hand"])
        bet = p_data["bet"]
        payout = 0

        if p_data["status"] == "blackjack":
            payout = int(bet * 2.5) if dealer_value != 21 else bet  # 3:2 payout, push on dealer BJ
            outcome = "BLACKJACK!" if payout > bet else "Pushed with Blackjack."
        elif p_data["status"] == "busted":
            payout = 0
            outcome = "Busted."
        elif dealer_busted or player_value > dealer_value:
            payout = bet * 2  # Win 1:1
            outcome = f"Wins ({player_value} vs {dealer_value})."
        elif player_value < dealer_value:
            payout = 0
            outcome = f"Loses ({player_value} vs {dealer_value})."
        else:  # Push
            payout = bet
            outcome = f"Pushed with {player_value}."

        await modify_coin_adjustment(p_id, payout)  # Give back winnings (original bet was already deducted)
        results_log.append(
            f"{'🎉' if payout > bet else '❌' if payout == 0 else '➖'} {p_data['member'].display_name}: {outcome}")
        p_data["bet"] = 0

    await _update_game_embed(channel_id, results_log=results_log)
    await asyncio.sleep(8)

    for member in table["waiting_to_join"]:
        if member.id not in table["players"]:
            table["players"][member.id] = {"member": member, "bet": 0, "hand": [], "status": "betting"}
    table["waiting_to_join"].clear()

    table["status"] = "waiting_for_bets"
    for p_data in table["players"].values():
        p_data["status"] = "betting"

    await _update_game_embed(channel_id)


async def _dealer_turn(channel_id: int):
    """The dealer plays their hand according to house rules."""
    table = active_blackjack_tables.get(channel_id)
    if not table: return

    await _update_game_embed(channel_id)
    await asyncio.sleep(1.5)

    while calculate_hand_value(table["dealer_hand"]) < 17 or (
            calculate_hand_value(table["dealer_hand"]) == 17 and any(c[1] == 'A' for c in table["dealer_hand"])):
        table["dealer_hand"].append(table["shoe"].pop())
        await _update_game_embed(channel_id)
        await asyncio.sleep(1.5)

    await _resolve_hand(channel_id)


async def _next_player_turn(channel_id: int):
    """Finds the next active player and gives them control."""
    table = active_blackjack_tables.get(channel_id)
    if not table: return

    next_player_id = None
    for p_id, p_data in table["players"].items():
        if p_data["status"] == "playing":
            next_player_id = p_id
            break

    table["current_player_id"] = next_player_id

    if next_player_id:
        await _update_game_embed(channel_id)
    else:
        table["status"] = "dealer_turn"
        await _dealer_turn(channel_id)


async def _initialize_table(logical_name: str):
    """Posts the initial message in a newly created channel."""
    table = active_blackjack_tables.get(logical_name)
    if not table:
        print(f"[BJ ERROR] Attempted to initialize non-existent logical table: {logical_name}")
        return

    channel = bot.get_channel(table["channel_id"])
    if not channel:
        print(f"[BJ ERROR] Could not find newly created channel for {logical_name}")
        return

    embed = discord.Embed(
        title=f"🎲 {logical_name} 🎲",
        description="The table is open. Place your bets to be included in the next hand!",
        color=discord.Color.dark_green()
    )
    # Pass the logical_name to the view
    new_message = await channel.send(embed=embed, view=BettingView(logical_name))
    table["game_message"] = new_message


async def _handle_player_leave(member: discord.Member, logical_name: str):
    """Handles a player leaving the game, and deletes the channel if they are the last one."""
    table = active_blackjack_tables.get(logical_name)
    if not table: return

    # Always remove the player from the lists if they exist.
    was_current_turn = table.get("current_player_id") == member.id
    player_data = table.get("players", {}).pop(member.id, None)
    table["waiting_to_join"] = [m for m in table.get("waiting_to_join", []) if m.id != member.id]

    # Refund bet if they had one placed
    if player_data and player_data.get("bet", 0) > 0:
        await modify_coin_adjustment(member.id, player_data["bet"])

    # --- CRITICAL CHECK: ARE THEY THE LAST PLAYER? ---
    if not table.get("players") and not table.get("waiting_to_join"):
        print(f"[BJ INFO] Last player left '{logical_name}'. Deleting channel.")
        channel_id = table.get("channel_id")
        channel = bot.get_channel(channel_id)

        if channel:
            try:
                await channel.delete(reason="Blackjack table closed.")
            except discord.Forbidden:
                print(f"[BJ CRITICAL ERROR] FAILED TO DELETE CHANNEL {channel_id}. BOT LACKS PERMISSIONS.")
            except discord.NotFound:
                pass # Channel was already gone.

        # Remove the table from the active state completely
        del active_blackjack_tables[logical_name]
        return # Stop execution here.

    # --- If players remain, update the game state ---
    channel = bot.get_channel(table['channel_id'])
    if channel:
       await channel.set_permissions(member, overwrite=None) # Revoke perms for the leaving player

    if was_current_turn:
        await _next_player_turn(logical_name)
    else:
        await _update_game_embed(logical_name)


async def _handle_player_join(member: discord.Member, logical_name: str):
    """Handles the logic for a player joining a table."""
    table = active_blackjack_tables.get(logical_name)
    if not table:
        print(f"[BJ ERROR] _handle_player_join called for a non-existent table: {logical_name}")
        return

    # --- If the game is already in progress, add the player to the waiting list ---
    if table["status"] in ["player_turns", "dealer_turn", "hand_over"]:
        # Prevent duplicate entries in the waiting list
        if not any(m.id == member.id for m in table["waiting_to_join"]):
            table["waiting_to_join"].append(member)

    # --- If the table is open for betting, add them as an active player ---
    else:
        if member.id not in table["players"]:
            table["players"][member.id] = {"member": member, "bet": 0, "hand": [], "status": "betting"}

        # If the table was brand new and waiting for its first player, change status
        if table["status"] == "waiting_for_players":
            table["status"] = "waiting_for_bets"

    # Finally, update the public game embed to show the new player
    await _update_game_embed(logical_name)


async def _start_new_hand(channel_id: int):
    """Resets the table for a new hand, deals cards, and transitions to player turns."""
    table = active_blackjack_tables.get(channel_id)
    if not table: return

    shoe_size = len(create_shoe(2))
    if len(table["shoe"]) < shoe_size * SHOE_RESHUFFLE_THRESHOLD:
        table["shoe"] = create_shoe(2)
        channel = bot.get_channel(channel_id)
        if channel: await channel.send("`DEALER: Shoe is low. Reshuffling...`", delete_after=10)
        await asyncio.sleep(2)

    table["dealer_hand"] = []

    for p_id in list(table["players"].keys()):
        if table["players"][p_id]["bet"] == 0:
            await _handle_player_leave(table["players"][p_id]["member"], channel_id)
        else:
            table["players"][p_id].update({"hand": [], "status": "playing"})

    if not table["players"]: return await _initialize_table(channel_id)

    # Deal Cards
    for _ in range(2):
        for p_id in table["players"]: table["players"][p_id]["hand"].append(table["shoe"].pop())
    table["dealer_hand"].extend([table["shoe"].pop(), table["shoe"].pop()])

    table["status"] = "player_turns"
    dealer_has_bj = calculate_hand_value(table["dealer_hand"]) == 21

    for p_id, p_data in table["players"].items():
        if calculate_hand_value(p_data["hand"]) == 21:
            p_data["status"] = "blackjack"

    await _update_game_embed(channel_id)
    await asyncio.sleep(1.5)

    if dealer_has_bj:
        await _resolve_hand(channel_id)
    else:
        # Before starting turns, check if all players have blackjack. If so, just resolve.
        if all(p.get("status") == "blackjack" for p in table["players"].values()):
            await _resolve_hand(channel_id)
        else:
            await _next_player_turn(channel_id)

# --- BLOCK 4: MODALS AND VIEWS ---
# (This block comes AFTER the core logic functions it uses)

class BetModal(ui.Modal, title="Place Your Bet"):
    def __init__(self, logical_name: str): # CHANGED
        super().__init__()
        self.logical_name = logical_name # CHANGED
        self.bet_amount = ui.TextInput(label="Bet Amount", placeholder="Enter a number or 'all'", required=True)
        self.add_item(self.bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        # --- CRITICAL FIX ---
        # 1. Defer the interaction IMMEDIATELY. This tells Discord "I'm working on it"
        #    and gives you a 15-minute window to respond. Using ephemeral=True means
        #    any follow-up error messages will only be visible to the user.
        await interaction.response.defer(ephemeral=True, thinking=False)

        table = active_blackjack_tables.get(self.logical_name)
        if not table or interaction.user.id not in table["players"]:
            # 2. Use followup.send for all messages after deferring.
            return await interaction.followup.send("You are not at this table.", ephemeral=True)

        player_data = table["players"][interaction.user.id]
        if player_data.get("bet", 0) > 0:
            return await interaction.followup.send("You have already placed a bet for this hand.", ephemeral=True)

        balance = await get_effective_balance(interaction.user.id)
        bet_str = self.bet_amount.value.lower().strip()

        try:
            amount = balance if bet_str == 'all' else int(bet_str)
        except ValueError:
            return await interaction.followup.send("Invalid bet amount.", ephemeral=True)

        if amount <= 0:
            return await interaction.followup.send("You must bet a positive amount.", ephemeral=True)
        if balance < amount:
            return await interaction.followup.send(f"You don't have enough coins! You have **{balance:,}**.",
                                                   ephemeral=True)

        # All checks passed, now we modify the game state.
        player_data["bet"] = amount
        await modify_coin_adjustment(interaction.user.id, -amount)  # Pre-deduct bet

        # 3. There is nothing left to "followup" with since the public embed will update.
        #    The deferral is complete. We just update the main game message.
        await _update_game_embed(self.logical_name) # CHANGED

class BettingView(ui.View):
    def __init__(self, logical_name: str): # CHANGED
        super().__init__(timeout=None)
        self.logical_name = logical_name # CHANGED

    @ui.button(label="Place Bet", style=discord.ButtonStyle.green, custom_id="bj_place_bet")
    async def place_bet(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BetModal(self.logical_name)) # CHANGED

    @ui.button(label="Start Hand", style=discord.ButtonStyle.primary, custom_id="bj_start_hand")
    async def start_hand(self, interaction: discord.Interaction, button: ui.Button):
        table = active_blackjack_tables.get(self.logical_name) # CHANGED
        if not table or interaction.user.id not in table["players"]:
            return  # Silently fail if the interactor is not a seated player

        total_players = len(table["players"])
        if total_players == 0:
            return  # Should not be possible to click, but a good safeguard

        # Count how many players have a bet greater than 0
        players_who_bet = sum(1 for p in table["players"].values() if p.get("bet", 0) > 0)

        # Calculate the required number of players (more than half)
        # We use math.ceil to correctly handle odd numbers. e.g., ceil(5 / 2) = 3.
        required_bettors = math.ceil(total_players / 2)

        # If we require at least 1 player, but the logic for > half would yield 1 for a 1-player game, let's ensure it's at least 1.
        if total_players == 1:
            required_bettors = 1
        else:
            # For 2+ players, "more than half" means floor(N/2) + 1
            required_bettors = (total_players // 2) + 1

        if players_who_bet < required_bettors:
            return await interaction.response.send_message(
                f"Cannot start the hand yet. "
                f"More than half the players must bet.\n"
                f"**{players_who_bet} / {total_players}** have bet. Need **{required_bettors}** to start.",
                ephemeral=True
            )

        # If the check passes, proceed with starting the hand.
        await interaction.response.defer()
        await _start_new_hand(self.logical_name) # CHANGED

    @ui.button(label="Leave Table", style=discord.ButtonStyle.danger, custom_id="bj_leave_table")
    async def leave_table(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await _handle_player_leave(interaction.user, self.logical_name)


class PlayerActionView(ui.View):
    def __init__(self, logical_name: str, can_double: bool): # CHANGED
        super().__init__(timeout=120.0)
        self.logical_name = logical_name # CHANGED
        self.double_down.disabled = not can_double

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        table = active_blackjack_tables.get(self.logical_name) # CHANGED
        if not table or interaction.user.id != table.get("current_player_id"):
            await interaction.response.send_message("It is not your turn.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        table = active_blackjack_tables.get(self.logical_name) # CHANGED
        if table and table["status"] == "player_turns":
            p_id = table["current_player_id"]
            if p_id in table["players"]:
                table["players"][p_id]["status"] = "stood"
                channel_id = table.get("channel_id")
                if channel_id:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        member_name = table['players'][p_id]['member'].display_name
                        await channel.send(f"{member_name} timed out and stood.", delete_after=10)

                # This part was already correct
                await _next_player_turn(self.logical_name)

    @ui.button(label="Hit", style=discord.ButtonStyle.green, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        table = active_blackjack_tables.get(self.logical_name)
        p_data = table["players"][interaction.user.id]
        p_data["hand"].append(table["shoe"].pop())
        self.double_down.disabled = True

        if calculate_hand_value(p_data["hand"]) >= 21:
            p_data["status"] = "busted" if calculate_hand_value(p_data["hand"]) > 21 else "stood"
            await _update_game_embed(self.logical_name)
            await asyncio.sleep(1)
            await _next_player_turn(self.logical_name)
        else:
            await _update_game_embed(self.logical_name)

    @ui.button(label="Stand", style=discord.ButtonStyle.danger, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        table = active_blackjack_tables.get(self.logical_name)
        table["players"][interaction.user.id]["status"] = "stood"
        await _next_player_turn(self.logical_name)

    @ui.button(label="Double Down", style=discord.ButtonStyle.primary, custom_id="bj_double")
    async def double_down(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        table = active_blackjack_tables.get(self.logical_name)
        p_data = table["players"][interaction.user.id]

        await modify_coin_adjustment(interaction.user.id, -p_data["bet"])
        p_data["bet"] *= 2
        p_data["hand"].append(table["shoe"].pop())
        p_data["status"] = "busted" if calculate_hand_value(p_data["hand"]) > 21 else "stood"

        await _update_game_embed(self.logical_name)
        await asyncio.sleep(1.5)
        await _next_player_turn(self.logical_name)


class TableSelectionView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        for logical_name in LOGICAL_TABLES:
            button = ui.Button(label=f"Join {logical_name}", style=discord.ButtonStyle.secondary,
                               custom_id=f"join_table_{logical_name}")
            button.callback = self.join_table_callback
            self.add_item(button)

    async def join_table_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        logical_name = interaction.data["custom_id"].split("join_table_")[-1]
        table_data = active_blackjack_tables.get(logical_name)

        # --- PATH A: TABLE ALREADY EXISTS ---
        if table_data:
            channel_id = table_data.get("channel_id")
            if not channel_id:
                return await interaction.followup.send("Error: Table state is corrupt.", ephemeral=True)

            player_count = len(table_data.get("players", {})) + len(table_data.get("waiting_to_join", []))
            if player_count >= MAX_PLAYERS_PER_TABLE:
                return await interaction.followup.send("This table is full.", ephemeral=True)
            if interaction.user.id in table_data.get("players", {}) or any(
                    m.id == interaction.user.id for m in table_data.get("waiting_to_join", [])):
                return await interaction.followup.send("You are already at this table.", ephemeral=True)

            target_channel = bot.get_channel(channel_id)
            if not target_channel:
                del active_blackjack_tables[logical_name]
                return await interaction.followup.send(
                    "Error: The game channel was not found and has been reset. Please try again.", ephemeral=True)

            await target_channel.set_permissions(interaction.user, read_messages=True, send_messages=True,
                                                 read_message_history=True)
            await interaction.followup.send(f"Joining {logical_name}! Click here: {target_channel.mention}",
                                            ephemeral=True)
            await _handle_player_join(interaction.user, logical_name)

        # --- PATH B: FIRST PLAYER, CREATE THE CHANNEL ---
        else:
            category = bot.get_channel(BLACKJACK_CATEGORY_ID)
            if not category:
                return await interaction.followup.send("CRITICAL ERROR: Blackjack category not found.", ephemeral=True)

            channel_name = LOGICAL_TABLES[logical_name]["name"]
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                                  manage_messages=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                              read_message_history=True)
            }

            try:
                new_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites,
                                                                 reason=f"Blackjack table '{logical_name}' created.")
            except discord.Forbidden:
                return await interaction.followup.send("CRITICAL ERROR: The bot lacks 'Manage Channels' permission.",
                                                       ephemeral=True)

            active_blackjack_tables[logical_name] = {
                "channel_id": new_channel.id,  # Store the new channel ID
                "shoe": create_shoe(2),
                "status": "waiting_for_bets",
                "players": {},  # Will be populated by _handle_player_join
                "dealer_hand": [],
                "game_message": None,
                "current_player_id": None,
                "waiting_to_join": [],
            }

            # Now that the state exists, formally join the player
            await _handle_player_join(interaction.user, logical_name)

            # Initialize the embed in the new channel
            await _initialize_table(logical_name)
            await interaction.followup.send(
                f"You have created {logical_name}! Click here to play: {new_channel.mention}", ephemeral=True)


# --- BLOCK 5: COMMAND AND ON_READY HOOK ---
# (This block comes last)

@bot.command(name="bj", aliases=["blackjack"])
async def blackjack_tables(ctx: commands.Context):
    """Shows the available Blackjack tables and allows joining."""
    embed = discord.Embed(
        title="Official Blackjack Tables",
        description="Choose a table to join. An empty table will create a new private game channel.",
        color=discord.Color.gold()
    )

    for logical_name in LOGICAL_TABLES:
        table_data = active_blackjack_tables.get(logical_name)
        player_list = "Empty"
        player_count = 0
        if table_data:
            players = table_data.get("players", {})
            waiting = table_data.get("waiting_to_join", [])
            player_count = len(players) + len(waiting)
            player_names = [p["member"].display_name for p in players.values()]
            player_names.extend([m.display_name for m in waiting])
            if player_names:
                player_list = ", ".join(player_names)

        embed.add_field(
            name=f"🎲 {logical_name} ({player_count}/{MAX_PLAYERS_PER_TABLE})", # MAX_PLAYERS_PER_TABLE can be a global int
            value=f"`{player_list}`",
            inline=False
        )

    await ctx.send(embed=embed, view=TableSelectionView())

# Balance
@bot.command(name="bal", aliases=["balance", "wallet"])
async def bal(ctx: commands.Context, member: discord.Member = None):
    """Displays a user's coin balance in a futuristic-themed embed."""

    # If no member is specified, the target is the person who ran the command.
    target_user = member or ctx.author

    # Prevent checking the balance of bots.
    if target_user.bot:
        return await ctx.send("`ANALYSIS FAILED: TARGET IS A NON-ECONOMIC UNIT (BOT).`")

    # --- 1. Initial "Processing" Message ---
    # This builds suspense and makes the command feel more interactive.
    processing_embed = discord.Embed(
        title="ACCESSING WALLET DATASTREAM...",
        description=f"`Requesting asset profile for operator: {target_user.name}`",
        color=0x206694 # A dark, techy color
    )
    processing_msg = await ctx.send(embed=processing_embed)

    # --- 2. Fetch All Necessary Balance Data ---
    # We get the total balance and also the components for a breakdown.
    try:
        total_balance = await get_effective_balance(target_user.id)
        stats_balance = await calculate_total_coins_from_stats(target_user.id)
        gambling_adjustment = await get_coin_adjustment(target_user.id)
    except Exception as e:
        await processing_msg.edit(content=f"`CRITICAL ERROR: Could not retrieve financial data. Log: {e}`", embed=None)
        return

    # --- 3. Build the Final Futuristic Embed ---
    final_embed = discord.Embed(
        title="<:wbcoin:1398780929664745652> DIGITAL ASSET PROFILE",
        color=0x00FFFF # A bright, neon "cyberpunk" color
    )

    # Use the target's avatar and name in the author field for personalization.
    final_embed.set_author(name=f"IDENTITY SCAN: {target_user.display_name}", icon_url=target_user.display_avatar.url)

    # Add the breakdown field for more detail. The ">" creates a nice blockquote effect.
    final_embed.add_field(
        name="[ ASSET ANALYSIS ]",
        value=f"> Stat-Based Earnings: `{stats_balance:,}`\n"
              f"> Gambling Net Profit/Loss: `{gambling_adjustment:,}`",
        inline=False
    )

    # The main event: the total balance, formatted to stand out.
    final_embed.add_field(
        name="[ CURRENT HOLDINGS ]",
        value=f"<:wbcoin:1398780929664745652> `{total_balance:,}`", # "##" makes the text larger
        inline=False
    )

    # --- 4. Final Update ---

    # Edit the original message to replace the "processing" embed with the final one.
    await processing_msg.edit(embed=final_embed)

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

# Roulette
class JoinGameModal(ui.Modal, title='Join Roulette Table'):
    def __init__(self, parent_view: 'MultiplayerRouletteView'):
        super().__init__()
        self.parent_view = parent_view
        self.buy_in_input = ui.TextInput(label="How many chips to bring to the table?",
                                         placeholder="Enter a number or 'all'", required=True)
        self.add_item(self.buy_in_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        game_state = active_roulette_games.get(interaction.message.id)
        if not game_state: return await interaction.followup.send("This game no longer exists.", ephemeral=True)
        player_id = interaction.user.id
        if player_id in game_state["players"]: return await interaction.followup.send("You have already joined.",
                                                                                      ephemeral=True)

        player_balance = await get_effective_balance(player_id)
        buy_in_str = self.buy_in_input.value.lower()
        try:
            buy_in_amount = player_balance if buy_in_str == 'all' else int(buy_in_str)
        except ValueError:
            return await interaction.followup.send("Invalid amount.", ephemeral=True)

        if buy_in_amount <= 0: return await interaction.followup.send("Must bring a positive amount.", ephemeral=True)
        if player_balance < buy_in_amount: return await interaction.followup.send(
            f"Not enough coins! You have {player_balance:,}.", ephemeral=True)

        game_state["players"][player_id] = {"name": interaction.user.display_name, "buy_in": buy_in_amount,
                                            "chips_placed": 0, "bets": {}}
        embed = self.parent_view.update_embed(game_state)
        await interaction.message.edit(embed=embed, view=self.parent_view)
        await interaction.followup.send(f"You have successfully joined the table with {buy_in_amount:,} chips!",
                                        ephemeral=True)


# --- NEW MODAL FOR PLACING MULTIPLE BETS AT ONCE ---
class RouletteMultiBetModal(ui.Modal, title='Place Group Bets'):
    def __init__(self, selected_bets: list[str], parent_view: 'MultiplayerRouletteView'):
        super().__init__()
        self.selected_bets = selected_bets
        self.parent_view = parent_view

        # --- THE FIX ---
        # Move the list of bets from the unsupported 'description'
        # into a multi-line 'label'.
        bet_list_str = ", ".join(selected_bets)
        self.amount_input = ui.TextInput(
            label=f"Bet on: {bet_list_str}",  # The bets are now in the label
            placeholder="Amount to bet on EACH selection (e.g., 100)",
            required=True
        )
        # --- END OF FIX ---
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        # We must defer the interaction first, then loop.
        # Otherwise, the loop can cause a timeout on the interaction itself.
        await interaction.response.defer()

        # This part of the logic remains correct.
        # Loop through each bet the user selected and process it.
        # We need to use a standard 'for' loop, not a list comprehension,
        # because the function we call is async.
        for bet_name in self.selected_bets:
            await _process_bet_submission(interaction, self.parent_view, bet_name, self.amount_input.value)

class RouletteSingleNumberBetModal(ui.Modal, title='Bet on a Single Number'):
    def __init__(self, parent_view: 'MultiplayerRouletteView'):
        super().__init__()
        self.parent_view = parent_view
        self.number_input = ui.TextInput(label="Number to bet on (0-36, or 00)", required=True, max_length=2)
        self.amount_input = ui.TextInput(label="Amount to bet", placeholder="Enter a number or 'all'", required=True)
        self.add_item(self.number_input);
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        number_str = self.number_input.value.strip()
        valid_numbers = {str(i) for i in range(37)} | {"00"}
        if number_str not in valid_numbers:
            return await interaction.followup.send(f"'{number_str}' is not a valid number.", ephemeral=True)
        # Process this single bet
        await _process_bet_submission(interaction, self.parent_view, f"Number: {number_str}", self.amount_input.value)


# --- MODIFIED VIEW & SELECT MENU FOR GROUP BETS ---

class BetSelectMenu(ui.Select):
    def __init__(self, parent_view: 'MultiplayerRouletteView'):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="Red (1:1)", value="Red", emoji="🔴"),
            discord.SelectOption(label="Black (1:1)", value="Black", emoji="⚫"),
            discord.SelectOption(label="Odd (1:1)", value="Odd"),
            discord.SelectOption(label="Even (1:1)", value="Even"),
            discord.SelectOption(label="Low (1-18) (1:1)", value="1-18"),
            discord.SelectOption(label="High (19-36) (1:1)", value="19-36"),
            discord.SelectOption(label="1st Dozen (1-12) (2:1)", value="1st Dozen"),
            discord.SelectOption(label="2nd Dozen (13-24) (2:1)", value="2nd Dozen"),
            discord.SelectOption(label="3rd Dozen (25-36) (2:1)", value="3rd Dozen"),
        ]
        # --- THE FIX ---
        # Allow selecting multiple options up to the number of options available
        super().__init__(placeholder="Select one or more bets to place...", min_values=1, max_values=len(options),
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        # self.values is now a list of all selected bets
        await interaction.response.send_modal(
            RouletteMultiBetModal(selected_bets=self.values, parent_view=self.parent_view))


class BetSelectionView(ui.View):
    def __init__(self, parent_view: 'MultiplayerRouletteView'):
        super().__init__(timeout=60)
        self.add_item(BetSelectMenu(parent_view))


# --- CORE GAME VIEW & LOGIC ---

class MultiplayerRouletteView(ui.View):
    def __init__(self, host_id: int):
        super().__init__(timeout=600.0)
        self.host_id = host_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        game_state = active_roulette_games.get(interaction.message.id)
        if not game_state: return False
        if interaction.data.get("custom_id") == "join_game": return True
        if interaction.data.get("custom_id") == "spin_wheel":
            if interaction.user.id != self.host_id:
                await interaction.response.send_message("Only the host can spin the wheel.", ephemeral=True)
                return False
            return True
        if interaction.user.id in game_state["players"]: return True
        await interaction.response.send_message("You need to join the game first before placing bets!", ephemeral=True)
        return False

    def update_embed(self, game_state: dict) -> discord.Embed:
        embed = discord.Embed(title="🎲 Community Roulette Table 🎲",
                              description="The betting phase is open! Click 'Join Game' to buy in.",
                              color=discord.Color.dark_red())
        player_list = []
        for pdata in game_state["players"].values():
            bet_details = " ".join([f"`{b.replace(' Dozen', 'D')}:{a}`" for b, a in pdata["bets"].items()])
            player_list.append(f"**{pdata['name']}**: `{pdata['buy_in'] - pdata['chips_placed']:,}` left {bet_details}")
        embed.add_field(name="Players & Bets",
                        value="\n".join(player_list) if player_list else "No one has joined yet.", inline=False)
        host_name = "..."
        if self.host_id in game_state["players"]: host_name = game_state["players"][self.host_id]["name"]
        embed.set_footer(text=f"Table hosted by {host_name} | Click 'Spin!' when betting is done.")
        return embed

    async def on_timeout(self):
        if self.message and self.message.id in active_roulette_games: del active_roulette_games[self.message.id]
        for item in self.children: item.disabled = True
        if self.message: await self.message.edit(content="This roulette table has expired.", embed=None, view=self)

    @ui.button(label="Join Game", style=discord.ButtonStyle.success, custom_id="join_game", row=0)
    async def join_game(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(JoinGameModal(self))

    @ui.button(label="Spin the Wheel!", style=discord.ButtonStyle.danger, custom_id="spin_wheel", row=0)
    async def spin_wheel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        game_state = active_roulette_games.get(interaction.message.id)
        if not game_state or not game_state["players"]: return await interaction.followup.send(
            "Cannot spin, no players.", ephemeral=True)
        if all(p['chips_placed'] == 0 for p in game_state["players"].values()): return await interaction.followup.send(
            "At least one player must bet.", ephemeral=True)
        for item in self.children: item.disabled = True
        await interaction.edit_original_response(view=self)
        await _run_roulette_spin(interaction, game_state)

    @ui.button(label="Place Group Bet(s)", style=discord.ButtonStyle.primary, row=1)
    async def bet_group(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Choose your bet(s) from the dropdown below.",
                                                view=BetSelectionView(self), ephemeral=True)

    @ui.button(label="Bet on Single Number", style=discord.ButtonStyle.secondary, row=1)
    async def bet_single(self, i: discord.Interaction, b: ui.Button):
        await i.response.send_modal(RouletteSingleNumberBetModal(self))


async def _process_bet_submission(interaction: discord.Interaction, view: 'MultiplayerRouletteView', bet_name: str,
                                  amount_str: str):
    game_state = active_roulette_games.get(view.message.id)
    if not game_state: return
    player_data = game_state["players"].get(interaction.user.id)
    if not player_data: return

    chips_remaining = player_data["buy_in"] - player_data["chips_placed"]
    try:
        amount_each = chips_remaining if amount_str.lower() == 'all' else int(amount_str)
    except ValueError:
        return await interaction.followup.send("Invalid amount.", ephemeral=True)

    if amount_each <= 0: return await interaction.followup.send("Bet must be positive.", ephemeral=True)
    if amount_each > chips_remaining: return await interaction.followup.send(
        f"You don't have enough chips for that bet! You only have {chips_remaining:,} left.", ephemeral=True)

    player_data["bets"][bet_name] = player_data["bets"].get(bet_name, 0) + amount_each
    player_data["chips_placed"] += amount_each

    embed = view.update_embed(game_state)
    await view.message.edit(embed=embed, view=view)


async def _run_roulette_spin(interaction: discord.Interaction, game_state: dict):
    # This function is now perfect and doesn't need changes.
    winning_key = random.choice(list(ROULETTE_POCKETS.keys()))
    winning_number = int(winning_key) if str(winning_key).isdigit() else winning_key
    winning_color = ROULETTE_POCKETS[winning_key]

    await interaction.edit_original_response(
        embed=discord.Embed(title="No More Bets!", description="The wheel is spinning...", color=0x7289DA), view=None)
    await asyncio.sleep(2)

    color_emoji = "🔴" if winning_color == "red" else "⚫" if winning_color == "black" else "🟢"
    final_embed = discord.Embed(title="✨ Wheel Landed! ✨",
                                description=f"The ball landed on **{color_emoji} {winning_key} {color_emoji}**",
                                color=discord.Color.gold())

    player_results_text = []
    for player_id, p_data in game_state["players"].items():
        total_payout = 0
        for bet_name, amount in p_data["bets"].items():
            won, rate = False, 0
            if bet_name.startswith("Number: "):
                if bet_name.split(": ")[1] == str(winning_key): won, rate = True, 35
            elif winning_number not in [0, '00']:
                if bet_name == "Red" and winning_color == "red":
                    won, rate = True, 1
                elif bet_name == "Black" and winning_color == "black":
                    won, rate = True, 1
                elif bet_name == "Odd" and winning_number % 2 != 0:
                    won, rate = True, 1
                elif bet_name == "Even" and winning_number % 2 == 0:
                    won, rate = True, 1
                elif bet_name == "1-18" and winning_number in range(1, 19):
                    won, rate = True, 1
                elif bet_name == "19-36" and winning_number in range(19, 37):
                    won, rate = True, 1
                elif bet_name == "1st Dozen" and winning_number in DOZEN_1:
                    won, rate = True, 2
                elif bet_name == "2nd Dozen" and winning_number in DOZEN_2:
                    won, rate = True, 2
                elif bet_name == "3rd Dozen" and winning_number in DOZEN_3:
                    won, rate = True, 2
            if won: total_payout += (amount * rate) + amount

        net_result = total_payout - p_data["chips_placed"]
        await modify_coin_adjustment(player_id, net_result)

        result_symbol = "📈" if net_result > 0 else "📉" if net_result < 0 else "➖"
        player_results_text.append(f"{result_symbol} **{p_data['name']}**: net `{net_result:+,}` coins.")

    final_embed.add_field(name="Player Results",
                          value="\n".join(player_results_text) if player_results_text else "No bets were placed.",
                          inline=False)
    await interaction.edit_original_response(embed=final_embed, view=None)
    if interaction.message.id in active_roulette_games: del active_roulette_games[interaction.message.id]


@bot.command(name="roulette")
async def roulette(ctx: commands.Context):
    """Starts a multiplayer roulette table in the channel."""
    if any(ctx.author.id in g.get("players", {}) for g in active_roulette_games.values()):
        return await ctx.send("You are already in an active roulette game somewhere else!")

    view = MultiplayerRouletteView(host_id=ctx.author.id)
    game_state = {"host_id": ctx.author.id, "players": {}, "status": "betting"}
    embed = view.update_embed(game_state)

    game_message = await ctx.send(embed=embed, view=view)
    view.message = game_message
    active_roulette_games[game_message.id] = game_state


@bot.command(name="addcoins", aliases=["award"])
async def addcoins(ctx: commands.Context, member: discord.Member, amount: int):
    """
    Awards a specified amount of coins to a user. (Admin Only)

    This command can also be used to remove coins by providing a negative number.
    """
    # 1. --- VALIDATION ---
    if member.bot:
        return await ctx.send("❌ You cannot give coins to a bot.")
    if amount == 0:
        return await ctx.send("❌ The amount cannot be zero.")

    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this powerful command.")

    # 2. --- THE TRANSACTION ---
    try:
        # We use the existing function to modify the user's coin total.
        # This works for both positive (adding) and negative (removing) amounts.
        success = await modify_coin_adjustment(member.id, amount)
        if not success:
            await ctx.send("❌ A database error occurred. The transaction could not be completed.")
            return

    except Exception as e:
        await ctx.send(f"❌ An unexpected error occurred: {e}")
        print(f"[ERROR] An exception occurred during the addcoins command: {e}")
        return

    # 3. --- CONFIRMATION ---
    # Fetch the user's new balance to display it for confirmation.
    new_balance = await get_effective_balance(member.id)

    # Create a clear and informative embed for the log/confirmation.
    action_text = "Awarded" if amount > 0 else "Deducted"
    color = discord.Color.green() if amount > 0 else discord.Color.red()

    embed = discord.Embed(
        title=f"✅ Admin Action: Coins {action_text}",
        description=f"**{abs(amount):,}** <:wbcoin:1398780929664745652> have been {action_text.lower()} for {member.mention}.",
        color=color
    )

    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Target User", value=member.mention, inline=True)
    embed.add_field(name=f"{member.display_name}'s New Balance", value=f"{new_balance:,} <:wbcoin:1398780929664745652>",
                    inline=False)
    embed.set_footer(text="The change has been successfully applied.")

    await ctx.send(embed=embed)


@addcoins.error
async def addcoins_error(ctx, error):
    """Handles errors for the addcoins command specifically."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have the required `Administrator` permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Incorrect usage. You need to specify a member and an amount.\n**Example:** `!addcoins @User 50000`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Couldn't find that member or the amount provided was not a valid number.")
    else:
        # For other errors, you might want them to go to your general error handler
        print(f"An unhandled error occurred in the addcoins command: {error}")


@bot.command(name="removestats", aliases=["rempoints"])
async def removestats(ctx: commands.Context, member: discord.Member, category: str, amount: int):
    """
    Removes a specified amount of points from a user in a specific category. (Admin Only)

    Valid Categories: messages, bugs, ideas, voice
    This command does NOT affect coins or trivia. Use !addcoins for coin changes.
    """
    # --- 1. Input Validation ---
    category = category.lower()
    if member.bot:
        return await ctx.send("❌ You cannot modify stats for a bot.")
    if amount <= 0:
        return await ctx.send("❌ The amount to remove must be a positive number.")

    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this powerful command.")

    # --- 2. Map Category to Database Table and Column ---
    # This dictionary makes the code clean and easy to expand
    table_map = {
        "messages": ("messages", "count"),
        "bugs": ("bug_points", "count"),
        "ideas": ("idea_points", "count"),
        "voice": ("voice_time", "seconds")
    }

    if category not in table_map:
        valid_cats = ", ".join(table_map.keys())
        await ctx.send(f"❌ Invalid category. Please use one of the following: `{valid_cats}`")
        return

    table_name, column_name = table_map[category]

    # --- 3. Database Interaction ---
    try:
        async with aiosqlite.connect("server_data.db") as db:
            # First, get the user's current score to ensure we don't go below zero
            cursor = await db.execute(f"SELECT {column_name} FROM {table_name} WHERE user_id = ?", (member.id,))
            row = await cursor.fetchone()

            current_score = row[0] if row else 0

            if current_score < amount:
                return await ctx.send(
                    f"❌ Cannot remove that many points.\n"
                    f"**{member.display_name}** only has **{current_score:,}** points in the `{category}` category."
                )

            # Perform the subtraction
            await db.execute(f"UPDATE {table_name} SET {column_name} = {column_name} - ? WHERE user_id = ?",
                             (amount, member.id))
            await db.commit()

            # Get the new score for confirmation
            cursor = await db.execute(f"SELECT {column_name} FROM {table_name} WHERE user_id = ?", (member.id,))
            new_score = (await cursor.fetchone())[0]

    except Exception as e:
        await ctx.send(f"❌ An unexpected database error occurred: {e}")
        print(f"[ERROR] An exception occurred during the removestats command: {e}")
        return

    # --- 4. Confirmation Embed ---
    unit = "seconds" if category == "voice" else "points"
    embed = discord.Embed(
        title="✅ Admin Action: Stats Removed",
        description=f"Successfully removed points from **{member.display_name}**.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
    embed.add_field(name="Target User", value=member.mention, inline=False)
    embed.add_field(name="Category", value=f"`{category.capitalize()}`", inline=True)
    embed.add_field(name="Amount Removed", value=f"`{amount:,} {unit}`", inline=True)
    embed.add_field(name="Score Update", value=f"`{current_score:,}` ➡️ `{new_score:,}`", inline=False)

    await ctx.send(embed=embed)


@removestats.error
async def removestats_error(ctx, error):
    """Handles errors for the removestats command."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have the required `Administrator` permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Incorrect usage. You need to specify a member, a category, and an amount.\n**Example:** `!removestats @User messages 100`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Couldn't find that member or the amount provided was not a valid whole number.")
    else:
        print(f"An unhandled error occurred in the removestats command: {error}")


@bot.command(name="deletechannel", aliases=["delchannel", "removechannel"])
async def delete_channel(ctx: commands.Context, channel_id: int):
    """
    Deletes the channel with the given ID.
    """
    # Try to fetch the channel
    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this powerful command.")

    channel = bot.get_channel(channel_id)

    if not channel:
        await ctx.send("❌ Could not find a channel with that ID.")
        return

    # Double-check it's in the same guild
    if channel.guild != ctx.guild:
        await ctx.send("❌ That channel doesn't belong to this server.")
        return

    try:
        await channel.delete(reason=f"Deleted by {ctx.author} via command.")
        await ctx.send(f"✅ Channel **#{channel.name}** has been deleted.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete that channel.")
    except Exception as e:
        await ctx.send("❌ An unexpected error occurred.")
        print(f"[ERROR] Failed to delete channel {channel_id}: {e}")

@bot.command(name="resetcoins")
async def reset_coins(ctx: commands.Context):
    """
    DANGEROUS: Deletes all coin adjustments, resetting everyone's balance to be
    based purely on their historical server activity (stats).
    """
    # Use the same ID as your other admin commands for consistency
    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this powerful command.")

    # Send an initial confirmation/working message
    warning_message = await ctx.send(
        "⚠️ **WARNING:** This will reset all gambling wins/losses for every user on the server.\n"
        "Their coin balance will be recalculated purely from their stats (messages, voice, etc.).\n"
        "This action cannot be undone. **Resetting in 5 seconds...**"
    )
    await asyncio.sleep(5)

    try:
        await warning_message.edit(content="⚙️ Processing... Wiping coin adjustment data...")

        # Connect to the database and clear the target table
        async with aiosqlite.connect("server_data.db") as db:
            # This is the core of the reset. It deletes all records of wins/losses.
            await db.execute("DELETE FROM coin_adjustments")
            await db.commit()

        # Final success message
        await warning_message.edit(
            content="✅ **Success!** All coin balances have been reset. "
                    "Balances are now calculated exclusively from server activity stats."
        )
        print(f"[ADMIN] Coin balances were successfully reset by {ctx.author.name}.")

    except Exception as e:
        # Error handling
        await warning_message.edit(
            content=f"❌ **An error occurred:** Failed to reset coin balances. Please check the console.\n`{e}`"
        )
        print(f"[ERROR] A critical error occurred during the coin reset command: {e}")

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
