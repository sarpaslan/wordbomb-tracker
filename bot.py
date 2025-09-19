import discord
from discord import ui
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput
import logging
from dotenv import load_dotenv
import os
import aiosqlite
import random
import datetime
import time
from datetime import datetime, timedelta, timezone
import motor.motor_asyncio
import asyncio
import math
import unicodedata
from collections import defaultdict, deque
import aiohttp
import matplotlib.pyplot as plt
import io

# Load token
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# --- New Constants ---
# Ask Hector for this connection string and put it in your .env file
MONGO_URI = os.getenv('MONGO_URI')
# ID of the private channel where suggestions will be sent for approval
APPROVAL_CHANNEL_ID = 1395207582985097276  # <--- ⚠️ CHANGE THIS TO YOUR LM'S PRIVATE CHANNEL ID

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
    337177097342681088, # thycooon (de-DE), admin
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
    # 849827666064048178, #test
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
    # 1392345870384762961, # test
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
    1392393127700205680,  # music commands channel
    1328176869572612288,  # normal commands channel
    1349650156001431592,  # what channel
    1310645572373450782,  # en-US suggest words channel
    1331697536599064626,  # fr-FR suggest words channel
    1333229725761540137,  # de-DE suggest words channel
    1335339488762920991,  # es-ES suggest words channel
    1341035170588917760,  # id-ID suggest words channel
    1334948522436591717,  # tr-TR suggest words channel
    1371921886245818418,  # ru suggest words channel
    1367131592505557012,  # sv-SE suggest words channel
    1359967225410486352,  # it-IT suggest words channel
    1348116185278844979,  # tl-TL suggest words channel
    1342836273819418737,  # pt-BR suggest words channel
    1390240204459085844,  # nl suggest words channel
    1356433831498088502,  # mc-MC suggest words channel
    1409399526841782343,  # prompts channel
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
                          "!daily - Claim a daily reward!",
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

# --- BLACKJACK CONSTANTS AND STATE ---
SUITS = ["♠️", "♥️", "♦️", "♣️"]
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
DOZEN_1 = set(range(1, 13))
DOZEN_2 = set(range(13, 25))
DOZEN_3 = set(range(25, 37))

# This dictionary will hold all active games, with the user's ID as the key.
active_blackjack_games = {}
active_baccarat_games = {}
active_roulette_games = {}
active_coinflips = set()

SHOE_RESHUFFLE_THRESHOLD = 0.05  # This is fine to keep

BASE_DAILY_REWARD = 2500
DAILY_STREAK_MULTIPLIER = 1.05

# The channel where the "Create Ticket" button will be posted
TICKET_SETUP_CHANNEL_ID = 1395899736032018592
# The category where new ticket channels will be created
TICKET_CATEGORY_ID = 1395901776409923684
# The developer who will be added to all tickets
DEVELOPER_ID = 265196052192165888

# --- Word Bomb Mini-Game Constants ---
WORD_GAME_CHANNEL_ID = 1409399526841782343
PRACTICE_ROOM_COMMAND_CHANNEL_ID = 1409399526841782343

WORDBOMB_API_TOKEN = os.getenv("WORDBOMB_API_TOKEN")
WORDBOMB_API_BASE = "https://1266394578702041119.discordsays.com/.proxy/dictionary"
LOCALE_FOR_PROMPTS = "en-US"
MIN_WORD_LENGTH = 3

VALID_PROMPTS = {}

api_session = None
ALLOWED_NORMALIZED_CHARS = set("abcdefghijklmnopqrstuvwxyz'-")

ROUND_LENGTH = 120  # How many solves per round
ROUND_START_DIFFICULTY = 500 # The solve count for the first prompt of a round (easiest)
ROUND_END_DIFFICULTY = 30

RECENT_PROMPT_MEMORY_SIZE = 2000 # Avoid repeating the last 200 prompts
_recent_prompts = deque(maxlen=RECENT_PROMPT_MEMORY_SIZE)

PRACTICE_PROMPTS_CACHE = {}

STATUS_PANEL_CHANNEL_ID = 1412105214625972364
STATUS_API_URL = "https://api.wordbomb.io/api/status"

_status_panel_message = None


ROLE_BUTTON_CHANNEL_ID = 1345408094632415324

GAME_UPDATES_ROLE_ID = 1414412843931144283
DICTIONARY_UPDATES_ROLE_ID = 1415715630212190300

# --- ✅ NEW: HIERARCHICAL SERVER TAG ROLE CONFIGURATION ---
TAG_CHECK_GUILD_ID = 1266397242260983888

# This list defines the role hierarchy FROM HIGHEST to LOWEST.
# The bot will use this order to determine the correct S-role.
# Format: ("Base Role Name", "S-Role to Assign")
S_ROLE_HIERARCHY = [
    ("Moderator", "GM S"), # Special case
    ("Language Moderator", "Language Moderator S"),
    ("Supporter", "Supporter S"),
    ("Contributor", "Contributor S"),
    ("Word Scout", "Word Scout S"),
    ("Server Booster", "Server Booster S"),
    ("Veteran", "Veteran S"),
    ("Speaker", "Speaker S"),
    ("Talker", "Talker S"),
    ("Active", "Active S"),
    ("Word Bomber", "Word Bomber S"),
]

# Create a set of all S-role names for efficient lookups
ALL_S_ROLES = {s_role_name for _, s_role_name in S_ROLE_HIERARCHY}

SHOP_API_BASE_URL = "https://1266394578702041119.discordsays.com/.proxy/player/inventory/add"

SHOP_ITEMS = {
    "chest": {
        "price": 1_000_000,
        "emoji_id": 1418624648995930314,
        "api_id": "chest",
        "reward_text": "Gives **50,000** Coins & **5,000** EXP"
    },
    "ring": {
        "price": 700_000,
        "emoji_id": 1418624665311514645,
        "api_id": "ring",
        "reward_text": "Gives **10** Diamonds"
    },
    "helmet": {
        "price": 350_000,
        "emoji_id": 1418624657539469382,
        "api_id": "helmet",
        "reward_text": "Gives **5** Diamonds"
    }
}

@bot.event
async def on_ready():
    global client, db, questions_collection, rejected_questions_collection, api_session, _status_panel_message
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

    api_session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {WORDBOMB_API_TOKEN}"})
    print("[INFO] aiohttp session created with Authorization header.")

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
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS daily_claims (
                user_id INTEGER PRIMARY KEY,
                last_claim_date TEXT NOT NULL,
                streak INTEGER NOT NULL DEFAULT 1
            )
        """)
        # --- NEW TABLES FOR WORD BOMB MINI-GAME ---
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS word_minigame_solves (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS word_minigame_active (
                channel_id INTEGER PRIMARY KEY,
                current_prompt TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                start_timestamp TEXT NOT NULL,
                is_practice INTEGER NOT NULL DEFAULT 0,
                sub_count INTEGER,
                creator_id INTEGER -- The new column to track the user who created the room
            )
        """)
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS word_minigame_state (
                channel_id INTEGER PRIMARY KEY,
                last_solver_id INTEGER NOT NULL,
                current_streak INTEGER NOT NULL
            )
        """)

        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS word_minigame_round_state (
                channel_id INTEGER PRIMARY KEY,
                round_number INTEGER NOT NULL DEFAULT 1,
                turn_in_round INTEGER NOT NULL DEFAULT 1
            )
        """)
        # --- NEW TABLE FOR DAILY MESSAGE HISTORY ---
        await db_sqlite.execute("""
            CREATE TABLE IF NOT EXISTS daily_message_history (
                user_id INTEGER NOT NULL,
                message_date TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, message_date)
            )
        """)
        await db_sqlite.commit()

    # --- Load Word Game Assets ---
    refresh_prompt_cache.start()

    # --- ENHANCED: Word Game Restart Resilience ---
    print("[INFO] Checking for all active word games from before restart...")
    async with aiosqlite.connect("server_data.db") as db:
        # Fetch all game data, not just IDs
        cursor = await db.execute(
            "SELECT channel_id, message_id, is_practice, sub_count, creator_id FROM word_minigame_active")
        active_games = await cursor.fetchall()

        for channel_id, message_id, is_practice, sub_count, creator_id in active_games:
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"[WARN] Game channel/thread {channel_id} not found. Cleaning up from DB.")
                await db.execute("DELETE FROM word_minigame_active WHERE channel_id = ?", (channel_id,))
                continue  # Skip to the next game
            try:
                # Check if the prompt message still exists
                await channel.fetch_message(message_id)
                print(f"[SUCCESS] Game in '{channel.name}' ({channel_id}) is still active.")
            except discord.NotFound:
                # The message was deleted while the bot was offline. Start a new round.
                print(f"[WARN] Prompt message in '{channel.name}' was deleted while offline. Starting new round.")
                # We pass all the game's original parameters to the start function
                await start_new_word_game_round(
                    channel,
                    is_practice=bool(is_practice),
                    sub_count=sub_count,
                    creator_id=creator_id
                )
            except discord.Forbidden:
                print(f"[ERROR] Lacking permissions to check for prompt message in '{channel.name}'.")

    print("[INFO] Setting up the API status panel...")
    status_channel = bot.get_channel(STATUS_PANEL_CHANNEL_ID)
    if status_channel:
        # Search the last 10 messages to find our panel
        async for message in status_channel.history(limit=10):
            if message.author.id == bot.user.id:
                _status_panel_message = message
                print(f"[INFO] Found existing status panel message with ID: {message.id}")
                break
        if not _status_panel_message:
            print("[INFO] No existing status panel found, creating a new one...")
            try:
                placeholder_embed = discord.Embed(title="API Status", description="Initializing...")
                _status_panel_message = await status_channel.send(embed=placeholder_embed)
            except discord.Forbidden:
                print(f"[ERROR] Cannot send messages in the status panel channel ({STATUS_PANEL_CHANNEL_ID}). Feature disabled.")
    else:
        print(f"[ERROR] Status panel channel ({STATUS_PANEL_CHANNEL_ID}) not found. Feature disabled.")

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
    bot.add_view(RoleButtonView())

    check_and_delete_old_threads.start()

    bot.add_view(TicketStarterView())
    bot.add_view(TicketCloseView())
    if _status_panel_message:
        if not update_status_panel.is_running():
            update_status_panel.start()


    print("-" * 20)
    print(f"[SUCCESS] Bot is ready. Logged in as {bot.user} ({bot.user.id})")
    print("-" * 20)


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
        async with db.execute("SELECT 1 FROM weekly_leaderboard_snapshot WHERE week = ?",
                              (previous_week_str,)) as cursor:
            if await cursor.fetchone():
                # print(f"[DEBUG] Snapshot for week {previous_week_str} already exists.")
                return  # We've already done this week, do nothing.

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
    await bot.wait_until_ready()  # Wait for the bot to be logged in before starting the loop


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()
    
    # --- UNIFIED COOLDOWN LOGIC ---
    last_time = last_message_times.get(user_id, 0)
    cooldown_passed = (now - last_time) >= 3
    
    if cooldown_passed:
        # Update the last message time for this user immediately.
        last_message_times[user_id] = now

    if not cooldown_passed:
        await bot.process_commands(message) # Still process commands on cooldown
        return

    # --- BLOCK 1: Daily Chart Tracking (Runs for ALL channels) ---
    async with aiosqlite.connect("server_data.db") as db:
        current_date = datetime.utcnow().strftime("%Y-%m-%d")
        await db.execute("""
            INSERT INTO daily_message_history (user_id, message_date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, message_date) DO UPDATE SET count = count + 1
        """, (user_id, current_date))
        await db.commit()

    is_practice_thread = isinstance(message.channel, discord.Thread) and message.channel.parent_id == PRACTICE_ROOM_COMMAND_CHANNEL_ID
    
    # This logic runs if it's not a practice thread AND not in the excluded list.
    if not is_practice_thread and message.channel.id not in EXCLUDED_CHANNEL_IDS:

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

    # --- Word Bomb Mini-Game Logic (Definitive Version with Character Validation) ---
    async with aiosqlite.connect("server_data.db") as db:
        # Step 1: Check if the message is in ANY active game channel (public or private thread)
        game_cursor = await db.execute(
            "SELECT current_prompt, start_timestamp, is_practice, sub_count, creator_id FROM word_minigame_active WHERE channel_id = ?",
            (message.channel.id,)
        )
        game_data = await game_cursor.fetchone()

        # Only proceed if a game is actually active in this channel
        if game_data:
            prompt, start_timestamp, is_practice, sub_count, creator_id = game_data

            original_input = message.content
            validation_input = original_input.replace(' ', '-') if ' ' in original_input else original_input

            if len(validation_input) >= MIN_WORD_LENGTH and message.created_at > datetime.fromisoformat(
                    start_timestamp).replace(tzinfo=timezone.utc):
                normalized_input = normalize_word(validation_input)

                # --- NEW: CHARACTER VALIDATION BLOCK ---
                # Check if every character in the normalized string is in our allowed set.
                if not all(char in ALLOWED_NORMALIZED_CHARS for char in normalized_input):
                    # The word contains invalid characters. Silently ignore it.
                    pass
                else:
                    # --- ORIGINAL LOGIC CONTINUES HERE ---
                    # If all characters are valid, we proceed with the API check.
                    contains_prompt = prompt in normalized_input

                    if contains_prompt and await is_word_valid_api(validation_input):
                        # --- VALID WORD SOLVED ---
                        delete_cursor = await db.execute("DELETE FROM word_minigame_active WHERE channel_id = ?", (message.channel.id,))
                        await db.commit()

                        if delete_cursor.rowcount > 0:
                            # --- WINNER'S LOGIC ---

                            reply_msg = (f"🎊 {message.author.mention} solved it with: 🎊\n\n"
                                        f"**{format_word_emojis(normalized_input, prompt=prompt)}**\n\n"
                                        "Round ended!")

                            full_reply = reply_msg

                            # --- Conditional Rewards ---
                            if not is_practice:
                                winner_id = message.author.id
                                channel_id = message.channel.id
                                _last_solved_prompt_info[channel_id] = [prompt, datetime.now(timezone.utc), False,
                                                                        winner_id]

                                new_round_announcement = None

                                cursor = await db.execute(
                                    "SELECT round_number, turn_in_round FROM word_minigame_round_state WHERE channel_id = ?",
                                    (channel_id,))
                                round_data = await cursor.fetchone()
                                round_num, turn_num = (round_data if round_data else (1, 0))

                                next_turn = turn_num + 1
                                if next_turn > ROUND_LENGTH:
                                    # A new round begins!
                                    round_num += 1
                                    next_turn = 1
                                    new_round_announcement = (f"🏁 **A new round has begun!** 🏁\n"
                                                              f"Prompts will gradually increase in difficulty!")

                                await db.execute("""
                                                    INSERT OR REPLACE INTO word_minigame_round_state (channel_id, round_number, turn_in_round)
                                                    VALUES (?, ?, ?)
                                                """, (channel_id, round_num, next_turn))
                                await db.commit()

                                # (Streak and ranking logic)
                                streak_cursor = await db.execute(
                                    "SELECT last_solver_id, current_streak FROM word_minigame_state WHERE channel_id = ?",
                                    (channel_id,))
                                last_streak_data = await streak_cursor.fetchone()
                                last_solver_id, old_streak = (last_streak_data if last_streak_data else (None, 0))
                                streak_message = ""
                                if last_solver_id == winner_id:
                                    new_streak = old_streak + 1
                                    if new_streak > 3: streak_message = f"{message.author.mention} is on a **{new_streak}** round streak! 🔥"
                                    await db.execute(
                                        "UPDATE word_minigame_state SET current_streak = ? WHERE channel_id = ?",
                                        (new_streak, channel_id))
                                else:
                                    if old_streak >= 3:
                                        try:
                                            old_solver_user = bot.get_user(last_solver_id) or await bot.fetch_user(
                                                last_solver_id)
                                            streak_message = f"{message.author.mention} broke {old_solver_user.mention}'s streak of **{old_streak}**! 💔"
                                        except discord.NotFound:
                                            streak_message = f"{message.author.mention} broke a streak of **{old_streak}**!"
                                    await db.execute(
                                        "INSERT OR REPLACE INTO word_minigame_state (channel_id, last_solver_id, current_streak) VALUES (?, ?, 1)",
                                        (channel_id, winner_id))
                                await db.commit()

                                current_data_cursor = await db.execute(
                                    "SELECT count FROM word_minigame_solves WHERE user_id = ?", (winner_id,))
                                current_data = await current_data_cursor.fetchone()
                                is_first_solve = current_data is None
                                current_solves = 0 if is_first_solve else current_data[0]
                                old_rank_cursor = await db.execute(
                                    "SELECT COUNT(*) + 1 FROM word_minigame_solves WHERE count > ?", (current_solves,))
                                old_rank = (await old_rank_cursor.fetchone())[0]
                                await db.execute(
                                    "INSERT INTO word_minigame_solves (user_id, count) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1",
                                    (winner_id,))
                                await db.commit()
                                new_solves = current_solves + 1
                                new_rank_cursor = await db.execute(
                                    "SELECT COUNT(*) + 1 FROM word_minigame_solves WHERE count > ?", (new_solves,))
                                new_rank = (await new_rank_cursor.fetchone())[0]
                                rank_msg = ""
                                if is_first_solve:
                                    total_players_cursor = await db.execute("SELECT COUNT(*) FROM word_minigame_solves")
                                    total_players = (await total_players_cursor.fetchone())[0]
                                    rank_msg = f"You're on the board at rank **#{new_rank}** out of {total_players} players! 🎉"
                                elif new_rank < old_rank:
                                    rank_change = old_rank - new_rank
                                    rank_msg = f"You moved up **{rank_change}** place{'s' if rank_change > 1 else ''}! You are now rank **#{new_rank}**! 📈"

                                if rank_msg: full_reply += f"\n{rank_msg}"
                                if streak_message: full_reply += f"\n{streak_message}"

                            await message.reply(full_reply, allowed_mentions=discord.AllowedMentions(users=False))
                            if not is_practice:
                                await asyncio.sleep(3)

                            # Correctly start the next round, passing the creator_id
                            await start_new_word_game_round(
                                message.channel,
                                is_practice=is_practice,
                                sub_count=sub_count,
                                creator_id=creator_id,
                                new_round_announcement=new_round_announcement
                            )

                        else:
                            # --- PATH B: WE WERE "TOO SLOW" ---
                            # THIS IS THE CORRECTLY NESTED LOGIC BLOCK
                            if not is_practice and message.channel.id in _last_solved_prompt_info:
                                last_prompt, solve_time, has_trash_talked, winner_id = _last_solved_prompt_info[
                                    message.channel.id]

                                if last_prompt in normalized_input and message.author.id != winner_id:
                                    time_since_solve = (message.created_at - solve_time).total_seconds()
                                    if not has_trash_talked and time_since_solve < 0.5:
                                        _last_solved_prompt_info[message.channel.id][2] = True
                                        trash_talk_line = random.choice(TRASH_TALK_LINES)
                                        reply_text = trash_talk_line.format(mention=message.author.mention)
                                        await message.reply(reply_text,
                                                            allowed_mentions=discord.AllowedMentions(users=False))

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


@bot.command(name="resetstreakstate")
async def reset_streak_state(ctx: commands.Context):
    """(Admin-only) Manually clears the word game's streak state from the DB."""
    DEVELOPER_IDS = [849827666064048178]
    if ctx.author.id not in DEVELOPER_IDS:
        return await ctx.send("🚫 You do not have permission to use this command.")

    async with aiosqlite.connect("server_data.db") as db:
        await db.execute("DELETE FROM word_minigame_state WHERE game_id = 1")
        await db.execute("DELETE FROM word_minigame_active WHERE channel_id = ?", (WORD_GAME_CHANNEL_ID,))
        await db.commit()

    await ctx.send("✅ Word game streak and active prompt state has been wiped. You can now start a new game.")

@bot.event
async def on_raw_reaction_add(payload):
    if POINT_LOGS_CHANNEL is None:
        print("[WARN] on_raw_reaction_add triggered before POINT_LOGS_CHANNEL was ready. Skipping event.")
        return

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
    except discord.NotFound:
        return

    # Point-log editing (no changes needed here, remains the same)
    if payload.channel_id == POINT_LOGS_CHANNEL.id and str(payload.emoji.name) == "✅":
        if payload.user_id not in DEVELOPER_IDS: return
        try:
            message_to_edit = await channel.fetch_message(payload.message_id)
            if not message_to_edit.embeds: return  # Safety check

            original_embed = message_to_edit.embeds[0]
            new_embed = original_embed.copy()
            new_embed.color = discord.Color.green()  # Change color to green

            # This logic to change the text remains the same
            lines = message_to_edit.content.splitlines()
            if not lines: return
            first_line, rest_of_message = lines[0], "\n".join(lines[1:])
            mention = message_to_edit.mentions[0].mention if message_to_edit.mentions else "the user"
            if first_line.startswith("🐞"):
                new_first_line = f"🟢 Fixed Bug, reported by {mention}"
                notification_message = f"✅ {mention}, your bug report has been marked as fixed by a developer! See the original log here: {message_to_edit.jump_url}. Thanks for contributing!"
            elif first_line.startswith("💡"):
                new_first_line = f"🟢 Implemented Idea by {mention}"
                notification_message = f"✅ {mention}, your suggestion has been implemented! See the original log here: {message_to_edit.jump_url}. Thanks for contributing!"
            else:
                return  # Don't edit if it's not a recognized format

            await message_to_edit.edit(content=new_first_line, embed=new_embed)

            try:
                # 2. Send a new, separate message to notify the user
                if notification_message:
                    await POINT_LOGS_CHANNEL.send(notification_message)
            except discord.Forbidden:
                print(f"[WARN] Bot doesn't have permission to send messages in the log channel.")
            except Exception as e:
                print(f"[ERROR] Failed to send notification message in log channel: {e}")

        except Exception as e:
            print(f"[ERROR] Failed to edit point log message: {e}")
        return

    # Bug / Idea system
    if payload.user_id not in DEVELOPER_IDS: return
    if payload.emoji.name not in emoji_channel_map: return

    expected_channel_id, pointed_table, points_table, role_name = emoji_channel_map[payload.emoji.name]

    if payload.channel_id != expected_channel_id: return

    # --- START: THE DEFINITIVE FORWARDED MESSAGE SOLUTION ---

    author_to_credit = None
    log_text = ""
    log_image_url = None
    is_forward = False

    # METHOD 1: The "Jump to URL" Workaround (Most Reliable)
    # This checks if the message has an embed with a valid "jump to message" URL.
    if reacted_message.embeds and reacted_message.embeds[0].url and "/channels/" in reacted_message.embeds[0].url:
        try:
            jump_url = reacted_message.embeds[0].url
            # Parse the URL: https://discord.com/channels/GUILD_ID/CHANNEL_ID/MESSAGE_ID
            url_parts = jump_url.split('/')
            original_channel_id = int(url_parts[-2])
            original_message_id = int(url_parts[-1])

            # Fetch the original channel and message
            source_channel = guild.get_channel(original_channel_id)
            if source_channel:
                original_message = await source_channel.fetch_message(original_message_id)

                # We found it! Extract data directly and reliably from the original message.
                author_to_credit = original_message.author
                log_text = original_message.content
                if original_message.attachments:
                    log_image_url = original_message.attachments[0].url

                is_forward = True  # Mark that we successfully handled this as a forward.
        except (ValueError, IndexError, discord.NotFound, discord.Forbidden):
            # This handles cases where the URL isn't a valid message link, the message was deleted,
            # or the bot doesn't have permissions to see the original channel.
            # We will let the code fall through to the less reliable methods.
            is_forward = False

    # This block runs for REGULAR messages OR if the URL method failed.
    if not is_forward:
        # METHOD 2: Regular Message with Attachments/Text
        if not reacted_message.embeds:
            author_to_credit = reacted_message.author
            # Your existing snapshot function is perfect for this.
            snapshot_data = await _fetch_message_snapshot(channel, reacted_message)
            log_text = snapshot_data['text']  # The function already formats this with "> "
            log_image_url = snapshot_data['image_url']

        # METHOD 3: Fallback for Failed Forwards or Other Embeds
        # This handles cases where the URL method failed but there's still an embed.
        else:
            embed = reacted_message.embeds[0]
            log_text = embed.description or ""
            if embed.image and embed.image.url:
                log_image_url = embed.image.url

            # For author, prioritize a manual @mention by the forwarder.
            if reacted_message.mentions and not reacted_message.mentions[0].bot:
                author_to_credit = reacted_message.mentions[0]
            else:
                # If no mention, credit the person who posted the forward.
                # This is more reliable than searching by name.
                author_to_credit = reacted_message.author

    # Final checks and formatting on the extracted content.
    if isinstance(log_text, str) and log_text.strip() and not log_text.startswith(">"):
        log_text = '\n'.join(f"> {line}" for line in log_text.splitlines())
    elif not log_text and not log_image_url:
        log_text = "> (No text content)"

    # Final check: Don't give points to bots or if author detection failed.
    if not author_to_credit or author_to_credit.bot:
        return

    # --- END: THE DEFINITIVE FORWARDED MESSAGE SOLUTION ---

    # --- Database Operations (now uses the correct author and message ID) ---
    async with aiosqlite.connect("server_data.db") as db:
        # Check if this specific reacted message already gave a point.
        async with db.execute(f"SELECT 1 FROM {pointed_table} WHERE message_id = ?", (reacted_message.id,)) as cursor:
            if await cursor.fetchone():
                return
        # If not, record it and award the point.
        await db.execute(f"INSERT INTO {pointed_table} (message_id) VALUES (?)", (reacted_message.id,))
        async with db.execute(f"SELECT count FROM {points_table} WHERE user_id = ?", (author_to_credit.id,)) as cursor:
            row = await cursor.fetchone()
        new_count = row[0] + 1 if row else 1
        if row:
            await db.execute(f"UPDATE {points_table} SET count = ? WHERE user_id = ?", (new_count, author_to_credit.id))
        else:
            await db.execute(f"INSERT INTO {points_table} (user_id, count) VALUES (?, ?)", (author_to_credit.id, 1))
        await db.commit()

    # --- Logging Logic (now uses the correctly sourced data) ---
    if POINT_LOGS_CHANNEL:
        log_title = ""
        if payload.emoji.name == BUG_EMOJI:
            log_title = f"🐞 Bug Reported by {author_to_credit.mention}"
        elif payload.emoji.name == IDEA_EMOJI:
            log_title = f"💡 Approved Idea by {author_to_credit.mention}"

        log_embed = discord.Embed(
            description=f"{log_text}\n\n🔗 [Jump to Message]({reacted_message.jump_url})",
            color=discord.Color.red()  # <-- ALWAYS RED
        )
        if log_image_url:
            log_embed.set_image(url=log_image_url)
        await POINT_LOGS_CHANNEL.send(content=log_title, embed=log_embed)

    # --- Role Assignment ---
    if new_count >= POINT_THRESHOLD:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(author_to_credit.id)
        if role and member and role not in member.roles:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"[WARN] Bot doesn't have permission to assign the '{role.name}' role.")


@bot.event
async def on_raw_reaction_remove(payload):
    """
    Handles when a developer un-reacts with a ✅, reverting the log message
    back to its original "In Progress" red state.
    """
    DEVELOPER_IDS = {265196052192165888, 849827666064048178}
    POINT_LOGS_CHANNEL_ID = 1392585590532341782

    # --- Validation: Only proceed if a dev removes a ✅ in the log channel ---
    if payload.channel_id != POINT_LOGS_CHANNEL_ID: return
    if str(payload.emoji.name) != "✅": return
    if payload.user_id not in DEVELOPER_IDS: return

    try:
        guild = bot.get_guild(payload.guild_id)
        if not guild: return
        channel = guild.get_channel(payload.channel_id)
        if not channel: return
        message_to_edit = await channel.fetch_message(payload.message_id)

        # Safety checks
        if not message_to_edit.embeds: return
        if not message_to_edit.mentions: return

        # --- Revert the Embed and Content ---
        original_embed = message_to_edit.embeds[0]
        new_embed = original_embed.copy()
        new_embed.color = discord.Color.red()  # Change color back to red

        # Determine the original message content based on the current content
        current_content = message_to_edit.content
        mention = message_to_edit.mentions[0].mention
        new_content = ""

        if current_content.startswith("🟢 Fixed Bug"):
            new_content = f"🐞 Bug Reported by {mention}"
        elif current_content.startswith("🟢 Implemented Idea"):
            new_content = f"💡 Approved Idea by {mention}"
        else:
            return  # Don't do anything if the format isn't recognized

        # Edit the message back to its original state
        await message_to_edit.edit(content=new_content, embed=new_embed)
        print(f"[INFO] Reverted point log message {message_to_edit.id} back to 'In Progress' state.")

    except Exception as e:
        print(f"[ERROR] Failed to revert point log message on reaction remove: {e}")


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
                cursor = await db.execute("SELECT join_time_iso FROM active_voice_sessions WHERE user_id = ?",
                                          (member.id,))
                session_row = await cursor.fetchone()

                if session_row:
                    # 2. Calculate the session duration.
                    join_time = datetime.fromisoformat(session_row[0])
                    duration_seconds = int((now - join_time).total_seconds())

                    # 3. Log the completed session to our new permanent table.
                    if duration_seconds > 5:  # Only log sessions longer than 5 seconds
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
                            if row and row[0] >= 1800000:
                                role = discord.utils.get(member.guild.roles, name="Voice Ambassador")
                                if role and role not in member.roles:
                                    if member.guild.me.top_role > role and member.guild.me.guild_permissions.manage_roles:
                                        await member.add_roles(role)
                                        print(f"[DEBUG] Gave Voice Ambassador role to {member.name}")

                    # 4. Clean up the temporary active session record.
                    await db.execute("DELETE FROM active_voice_sessions WHERE user_id = ?", (member.id,))
                    await db.commit()

    # --- HANDLING A USER JOINING A VOICE CHANNEL ---
    # This block runs if the user is in a valid channel after the update.
    if after.channel and after.channel.id not in EXCLUDED_VC_IDS:
        async with aiosqlite.connect("server_data.db") as db:
            # Create a new temporary session record with the current time.
            # "INSERT OR IGNORE" prevents errors if a session somehow already exists.
            await db.execute("INSERT OR IGNORE INTO active_voice_sessions (user_id, join_time_iso) VALUES (?, ?)",
                             (member.id, now.isoformat()))
            await db.commit()


async def get_coins_leaderboard_data() -> list:
    """
    Gathers all user stats, calculates their effective coin balance, sorts the
    results, and returns them as a list of (user_id, coin_count) tuples.
    This version is refactored to be explicitly stateless and prevent inconsistent results.
    """
    # --- Step 1: Gather each stat into its own dictionary ---
    message_counts = defaultdict(int)
    bug_counts = defaultdict(int)
    idea_counts = defaultdict(int)
    voice_seconds = defaultdict(int)
    adjustments = defaultdict(int)
    trivia_counts = defaultdict(int)
    
    # Gather from SQLite
    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute("SELECT user_id, count FROM messages") as cursor:
            async for user_id, count in cursor:
                message_counts[user_id] = count
        async with db.execute("SELECT user_id, count FROM bug_points") as cursor:
            async for user_id, count in cursor:
                bug_counts[user_id] = count
        async with db.execute("SELECT user_id, count FROM idea_points") as cursor:
            async for user_id, count in cursor:
                idea_counts[user_id] = count
        async with db.execute("SELECT user_id, seconds FROM voice_time") as cursor:
            async for user_id, seconds in cursor:
                voice_seconds[user_id] = seconds
        async with db.execute("SELECT user_id, adjustment_amount FROM coin_adjustments") as cursor:
            async for user_id, amount in cursor:
                adjustments[user_id] = amount

    # Gather from MongoDB
    if questions_collection is not None:
        try:
            pipeline = [
                {"$unionWith": {"coll": "rejected"}},
                {"$match": {"u": {"$ne": None}}}, # Filter out documents with null/missing user IDs
                {"$group": {"_id": "$u", "count": {"$sum": 1}}}
            ]
            cursor = questions_collection.aggregate(pipeline)
            async for doc in cursor:
                try:
                    # The user ID from Mongo is a string, so we keep it as is for now
                    user_id_str = doc["_id"]
                    if user_id_str:
                         trivia_counts[int(user_id_str)] = doc["count"]
                except (ValueError, KeyError, TypeError):
                    continue
        except Exception as e:
            print(f"[ERROR] Could not fetch bulk trivia stats for leaderboard: {e}")

    # --- Step 2: Get a set of all unique user IDs from all sources ---
    all_user_ids = set(message_counts.keys()) | set(bug_counts.keys()) | \
                   set(idea_counts.keys()) | set(voice_seconds.keys()) | \
                   set(adjustments.keys()) | set(trivia_counts.keys())

    # --- Step 3: Calculate totals in a single, deterministic loop ---
    leaderboard_entries = []
    for user_id in all_user_ids:
        message_coins = message_counts.get(user_id, 0) * 75
        bug_coins = bug_counts.get(user_id, 0) * 50000
        idea_coins = idea_counts.get(user_id, 0) * 40000
        voice_coins = int((voice_seconds.get(user_id, 0) / 3600) * 5000)
        trivia_coins = trivia_counts.get(user_id, 0) * 20000
        
        total_coins = message_coins + bug_coins + idea_coins + voice_coins + \
                      trivia_coins + adjustments.get(user_id, 0)

        if total_coins > 0:
            leaderboard_entries.append((user_id, total_coins))

    # --- Step 4: Sort and return the final, consistent data ---
    leaderboard_entries.sort(key=lambda item: item[1], reverse=True)
    return leaderboard_entries


class LeaderboardSelectMenu(discord.ui.Select):
    """The dropdown menu component for selecting a leaderboard."""

    def __init__(self):
        options = [
            discord.SelectOption(label="Messages", value="messages", description="Top chatters in the server.",
                                 emoji="💬"),
            discord.SelectOption(label="Word Game Solves", value="solves",
                                 description="Top WordBomb mini-game solvers.", emoji="💣"),
            discord.SelectOption(label="Trivia", value="trivia", description="Most approved trivia questions.",
                                 emoji="❓"),
            discord.SelectOption(label="Coins", value="coins", description="Richest users by total activity.",
                                 emoji="<:wbcoin:1398780929664745652>"),
            discord.SelectOption(label="Bugs", value="bugs", description="Top bug finders.", emoji="🐞"),
            discord.SelectOption(label="Ideas", value="ideas", description="Most approved ideas.", emoji="💡"),
            discord.SelectOption(label="Voice", value="voice", description="Most time spent in voice channels.",
                                 emoji="🎤"),
        ]
        super().__init__(placeholder="Choose a leaderboard category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # When a user selects an option, 'self.values[0]' will be the category name (e.g., "messages").
        # We then call the same update_leaderboard function as before.
        # 'interaction.view.author_id' gets the author's ID from the parent view.
        author_id = self.view.author_id
        selected_category = self.values[0]
        await update_leaderboard(interaction, selected_category, 1, author_id)


class CompactLeaderboardView(discord.ui.View):
    """The new, cleaner view with a dropdown and a single button."""

    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

        # Add the dropdown menu to the view
        self.add_item(LeaderboardSelectMenu())

        # Add the web profile button on the next row
        profile_url = f"https://discord.wordbomb.io/user/{self.author_id}"
        profile_button = discord.ui.Button(
            label="View Web Profile",
            style=discord.ButtonStyle.link,
            url=profile_url,
            emoji="🌐",
            row=1  # This places the button on the row below the dropdown
        )
        self.add_item(profile_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the original command author can use the dropdown."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            return False
        return True


async def update_leaderboard(ctx_or_interaction, category, page, author_id):
    table_map = {
        "messages": "messages",
        "bugs": "bug_points",
        "ideas": "idea_points",
        "voice": "voice_time",
        "solves": "word_minigame_solves"
    }
    label_map = {
        "trivia": ("question suggested", "questions suggested"),
        "messages": ("message", "messages"),
        "bugs": ("bug found", "bugs found"),
        "ideas": ("idea", "ideas"),
        "voice": ("second", "seconds"),
        "coins": ("coin", "coins"),
        "solves": ("solve", "solves")
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

    view = CompactLeaderboardView(author_id)
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
        language_mod_role = discord.utils.get(interaction.guild.roles, name="Language Moderator")
        language_mod_star_role = discord.utils.get(interaction.guild.roles, name="Language Moderator *")

        has_permission = (language_mod_role and language_mod_role in interaction.user.roles) or \
                         (language_mod_star_role and language_mod_star_role in interaction.user.roles) or \
                         interaction.user.id == 849827666064048178

        if not has_permission:
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
        language_mod_role = discord.utils.get(interaction.guild.roles, name="Language Moderator")
        language_mod_star_role = discord.utils.get(interaction.guild.roles, name="Language Moderator *")

        has_permission = (language_mod_role and language_mod_role in interaction.user.roles) or \
                         (language_mod_star_role and language_mod_star_role in interaction.user.roles) or \
                         interaction.user.id == 849827666064048178

        if not has_permission:
            await interaction.response.send_message("❌ You do not have permission to approve suggestions.",
                                                    ephemeral=True)
            return

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
        language_mod_role = discord.utils.get(interaction.guild.roles, name="Language Moderator")
        language_mod_star_role = discord.utils.get(interaction.guild.roles, name="Language Moderator *")

        has_permission = (language_mod_role and language_mod_role in interaction.user.roles) or \
                         (language_mod_star_role and language_mod_star_role in interaction.user.roles) or \
                         interaction.user.id == 849827666064048178

        if not has_permission:
            await interaction.response.send_message("❌ You do not have permission to approve suggestions.",
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
async def coinflip(ctx: commands.Context, amount_str: str):
    """
    Gamble your coins based on your total leaderboard stats.
    Usage: !cf <amount> OR !cf all (no max bet)
    """
    author = ctx.author
    MAX_BET = 100000  # The max bet for NUMERICAL bets only

    if author.id in active_coinflips:
        return await ctx.send("You already have a coinflip in progress! Please wait for it to finish.", ephemeral=True)

    # --- UPDATED: PARSE AND VALIDATE THE BET AMOUNT ---
    current_balance = await get_effective_balance(author.id)
    amount = 0
    is_all_in = False  # This flag will determine if we check the MAX_BET

    if amount_str.lower() == 'all':
        amount = current_balance
        is_all_in = True  # Set the flag to true for an "all in" bet
    else:
        try:
            amount = int(amount_str)
        except ValueError:
            return await ctx.send(f"❌ Invalid bet. Please enter a whole number or 'all'.")

    # --- UPDATED VALIDATION LOGIC ---
    if amount <= 0:
        # For 'all in', if a user has 0 coins, they can't bet. This check handles that.
        await ctx.send("❌ Your bet must be a positive amount.", ephemeral=True)
        return

    # Check the max bet limit, BUT ONLY if it's NOT an "all in" bet.
    if not is_all_in and amount > MAX_BET:
        await ctx.send(
            f"❌ The maximum bet is **{MAX_BET:,}** <:wbcoin:1398780929664745652>! Use `!cf all` to bet more.",
            ephemeral=True)
        return

    # Final check to ensure the user has enough coins.
    # This is slightly redundant for '!cf all' but acts as a crucial safety net against race conditions.
    if current_balance < amount:
        return await ctx.send(
            f"❌ You don't have enough coins! You only have **{current_balance:,}** <:wbcoin:1398780929664745652>.",
            ephemeral=True)

    # --- The rest of the function remains exactly the same ---
    active_coinflips.add(author.id)
    try:
        win_chance = 50
        won = random.randint(1, 100) <= win_chance
        net_change = amount if won else -amount
        success = await modify_coin_adjustment(author.id, net_change)

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

        await asyncio.sleep(animation_duration)

        if not success:
            error_embed = discord.Embed(title="Database Error",
                                        description="An error occurred saving the result. Please try again.",
                                        color=discord.Color.orange())
            await result_message.edit(embed=error_embed)
            active_coinflips.remove(author.id)
            return

        new_balance = current_balance + net_change
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
        print(f"[ERROR] An unexpected error occurred in coinflip: {e}")
        if author.id in active_coinflips:
            active_coinflips.remove(author.id)


@coinflip.error
async def coinflip_error(ctx, error):
    """Handles errors for the coinflip command."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Incorrect usage. You need to specify an amount or 'all'.\n"
            "**Examples:**\n`!cf 500`\n`!cf all`"
        )


# Blackjack

class BlackjackGame:
    """A class to represent the state of a single blackjack game."""

    def __init__(self, player, bet):
        self.player = player
        self.bet = bet
        # FIX: The shoe is now created with suits and ranks
        self.shoe = self._create_shoe(4)
        self.max_shoe_size = len(self.shoe)

        self.player_hand = []
        self.dealer_hand = []

        self.session_winnings = 0
        self.session_net = 0

        self.status = "playing"
        self.message = None

    # FIX: This function now creates a proper deck of (suit, rank) tuples.
    def _create_shoe(self, num_decks):
        """Creates and shuffles a multi-deck shoe."""
        shoe = []
        for _ in range(num_decks):
            for suit in SUITS:
                for rank in RANKS:
                    shoe.append((suit, rank))
        random.shuffle(shoe)
        return shoe

    def deal_card(self, hand):
        """Deals a single card from the shoe to a specified hand."""
        if len(self.shoe) < self.max_shoe_size * SHOE_RESHUFFLE_THRESHOLD:
            self.shoe = self._create_shoe(4)
        card = self.shoe.pop()
        hand.append(card)

    def initial_deal(self):
        """Performs the initial deal for player and dealer."""
        self.player_hand = []
        self.dealer_hand = []
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)


def calculate_hand_value(hand):
    """Calculates the value of a hand, handling Aces correctly."""
    # We access the rank via card[1]
    value = sum(RANKS[card[1]] for card in hand)
    # Check for aces by looking at card[1]
    num_aces = sum(1 for card in hand if card[1] == 'A')
    while value > 21 and num_aces:
        value -= 10
        num_aces -= 1
    return value


# FIX: Now correctly formats a hand of (suit, rank) tuples into a string.
def hand_to_string(hand, is_dealer_turn=False):
    """Converts a hand to a string, hiding the dealer's second card if necessary."""
    if not hand:
        return ""
    # For the dealer's initial turn, show the first card and a hidden card
    if not is_dealer_turn and len(hand) == 2:
        # Format the first card correctly from the tuple hand[0]
        return f"`{hand[0][0]} {hand[0][1]}` `[?]`"
    # For all other cases, format each (suit, rank) tuple
    return " ".join([f"`{card[0]} {card[1]}`" for card in hand])


async def create_game_embed(game: BlackjackGame, result_text=None, color=discord.Color.blue()):
    """Creates the main embed for the blackjack game."""
    player_balance = await get_effective_balance(game.player.id)

    embed = discord.Embed(color=color)
    embed.set_author(name=f"{game.player.display_name}'s Table", icon_url=game.player.display_avatar.url)

    # --- THIS IS THE CORRECTED PART ---
    # We now combine all stats into one field for cleaner formatting.
    stats_text = (
        f"<:wbcoin:1398780929664745652> **Your Balance:** {player_balance:,}\n"
        f"💸 **Current Bet:** {game.bet:,}\n"
        f"📈 **Session Net:** {game.session_net:+,}"
    )
    embed.add_field(name="Session Stats", value=stats_text, inline=False)
    # --- END OF CORRECTION ---

    # Dealer's hand
    dealer_value = calculate_hand_value(game.dealer_hand)
    is_dealer_turn = game.status == "hand_over"
    dealer_value_str = f"({dealer_value})" if is_dealer_turn else ""
    embed.add_field(
        name=f"Dealer's Hand {dealer_value_str}",
        value=hand_to_string(game.dealer_hand, is_dealer_turn),
        inline=False
    )

    # Player's hand
    player_value = calculate_hand_value(game.player_hand)
    embed.add_field(
        name=f"Your Hand ({player_value})",
        value=hand_to_string(game.player_hand, True),  # Always show player's full hand
        inline=False
    )

    if result_text:
        embed.description = result_text

    # Shoe progress footer
    embed.set_footer(text=f"Shoe: {len(game.shoe)} / {game.max_shoe_size} cards remaining")
    return embed


class ActionView(discord.ui.View):
    """The view with buttons for Hit, Stand, Double Down, and Surrender."""

    def __init__(self, game: BlackjackGame, player_balance: int):
        # FIX: Timeout is removed, making the view persistent.
        super().__init__(timeout=None)
        self.game = game

        if len(self.game.player_hand) != 2 or player_balance < self.game.bet:
            self.double_down.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # This check is now even more important to ensure the right player is interacting.
        if interaction.user.id != self.game.player.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def disable_all_buttons(self):
        """A helper function to disable all buttons in the view."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        # Edit the message to apply the disabled state visually
        if self.game.message:
            await self.game.message.edit(view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.game.deal_card(self.game.player_hand)
        player_value = calculate_hand_value(self.game.player_hand)

        if player_value >= 21:
            self.game.status = "hand_over"
            await handle_hand_end(self.game)
        else:
            self.double_down.disabled = True
            embed = await create_game_embed(self.game)
            await self.game.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.gray, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.game.status = "hand_over"
        await handle_hand_end(self.game)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, custom_id="bj_double")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # This check is a final failsafe, but the button should already be disabled if this is true.
        player_balance = await get_effective_balance(self.game.player.id)
        if player_balance < self.game.bet:
            await interaction.followup.send("You don't have enough coins to double down!", ephemeral=True)
            return
        await self.disable_all_buttons()
        await modify_coin_adjustment(self.game.player.id, -self.game.bet)
        self.game.bet *= 2
        self.game.deal_card(self.game.player_hand)
        self.game.status = "hand_over";
        await handle_hand_end(self.game)

    @discord.ui.button(label="Surrender", style=discord.ButtonStyle.red, custom_id="bj_surrender")
    async def surrender(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if len(self.game.player_hand) != 2:
            await interaction.followup.send("You can only surrender on your first move.", ephemeral=True)
            return

        self.game.status = "hand_over"

        refund = self.game.bet // 2
        await modify_coin_adjustment(self.game.player.id, refund)

        net_change = refund - self.game.bet
        self.game.session_winnings = refund
        self.game.session_net += net_change

        result_text = f"🏳️ You surrendered and got back {refund:,} coins."
        embed = await create_game_embed(self.game, result_text, color=discord.Color.red())
        await self.game.message.edit(embed=embed, view=PostHandView(self.game))


class PostHandView(discord.ui.View):
    """The view shown after a hand is over, with options to play again or quit."""

    def __init__(self, game: BlackjackGame):
        # FIX: Timeout is removed.
        super().__init__(timeout=None)
        self.game = game
        self.play_again_same_bet.label = f"Play Again ({self.game.bet:,})"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.game.player.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    # REMOVED: The on_timeout method is no longer needed.
    # async def on_timeout(self): ...

    @discord.ui.button(label="Play Again (Same Bet)", style=discord.ButtonStyle.green, custom_id="bj_play_again_same")
    async def play_again_same_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ... (this button's logic does not need to change) ...
        await interaction.response.defer()
        player_balance = await get_effective_balance(self.game.player.id)
        if player_balance < self.game.bet:
            embed = self.game.message.embeds[0]
            embed.description = f"❌ You don't have enough coins to place your last bet of {self.game.bet:,}."
            embed.color = discord.Color.dark_red()
            await self.game.message.edit(embed=embed, view=None)
            if interaction.message.id in active_blackjack_games:
                del active_blackjack_games[interaction.message.id]
            return
        await modify_coin_adjustment(self.game.player.id, -self.game.bet)
        self.game.initial_deal()
        self.game.status = "playing"
        self.game.session_winnings = 0
        player_value = calculate_hand_value(self.game.player_hand)
        if player_value == 21:
            self.game.status = "hand_over"
            await handle_hand_end(self.game)
        else:
            embed = await create_game_embed(self.game)
            view = ActionView(self.game, player_balance)
            await self.game.message.edit(embed=embed, view=view)

    @discord.ui.button(label="Play Again (New Bet)", style=discord.ButtonStyle.primary, custom_id="bj_play_again_new")
    async def play_again_new_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NewBetModal(self.game))

    @discord.ui.button(label="Quit", style=discord.ButtonStyle.red, custom_id="bj_quit")
    async def quit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        # FIX: The game is now removed from the active dictionary using its message ID.
        if interaction.message.id in active_blackjack_games:
            del active_blackjack_games[interaction.message.id]

        final_embed = await create_final_summary_embed(self.game)
        await self.game.message.edit(embed=final_embed, view=None)


class NewBetModal(discord.ui.Modal, title="Place a New Bet"):
    """A modal to get a new bet amount from the player."""

    def __init__(self, game: BlackjackGame):
        super().__init__()
        self.game = game
        self.new_bet_amount = discord.ui.TextInput(
            label="Enter your new bet amount",
            placeholder="e.g., 1000 or all",
            required=True
        )
        self.add_item(self.new_bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        player_balance = await get_effective_balance(self.game.player.id)
        bet_str = self.new_bet_amount.value.lower().strip()
        new_bet = 0

        if bet_str == 'all':
            new_bet = player_balance
        else:
            try:
                new_bet = int(bet_str)
            except ValueError:
                await interaction.followup.send("Invalid bet amount. Please enter a number or 'all'.", ephemeral=True)
                return

        if new_bet <= 0:
            await interaction.followup.send("Your bet must be a positive amount.", ephemeral=True)
            return

        if player_balance < new_bet:
            await interaction.followup.send(
                f"You don't have enough coins for that bet! Your balance is {player_balance:,}.", ephemeral=True)
            return

        self.game.bet = new_bet

        # FIX: The deduction now correctly uses the 'new_bet' variable.
        await modify_coin_adjustment(self.game.player.id, -new_bet)

        self.game.initial_deal()
        self.game.status = "playing"
        self.game.session_winnings = 0

        player_value = calculate_hand_value(self.game.player_hand)

        if player_value == 21:
            self.game.status = "hand_over"
            await handle_hand_end(self.game)
        else:
            embed = await create_game_embed(self.game)
            view = ActionView(self.game, player_balance)
            await self.game.message.edit(embed=embed, view=view)


async def create_final_summary_embed(game: BlackjackGame):
    """Creates a clean, final summary embed when a game session ends."""

    # Get the absolute final balance
    final_balance = await get_effective_balance(game.player.id)

    # Create a new, clean embed
    embed = discord.Embed(
        title="Blackjack Session Over",
        description="Thanks for playing! Here is your final summary.",
        color=discord.Color.dark_grey()
    )
    embed.set_author(name=f"{game.player.display_name}'s Table", icon_url=game.player.display_avatar.url)

    # Add ONLY the relevant final stats
    stats_text = (
        f"<:wbcoin:1398780929664745652> **Final Balance:** {final_balance:,}\n"
        f"📈 **Total Session Net:** {game.session_net:+,}"
    )
    embed.add_field(name="Final Stats", value=stats_text, inline=False)

    # No footer, no hands, no shoe status.
    return embed


async def handle_hand_end(game: BlackjackGame, custom_result_text=None):
    """Handles the logic at the end of a hand: dealer's turn, calculating results, and updating the message."""

    while calculate_hand_value(game.dealer_hand) < 17:
        game.deal_card(game.dealer_hand)

    player_value = calculate_hand_value(game.player_hand)
    dealer_value = calculate_hand_value(game.dealer_hand)

    winnings = 0
    result_text = ""
    final_color = discord.Color.red()

    is_player_bj = player_value == 21 and len(game.player_hand) == 2
    is_dealer_bj = dealer_value == 21 and len(game.dealer_hand) == 2

    if player_value > 21:
        result_text = f"❌ You busted with {player_value}!"
        winnings = 0
        final_color = discord.Color.red()
    elif is_player_bj and not is_dealer_bj:
        result_text = f"🎉 BLACKJACK! You win!"
        winnings = int(game.bet * 2.5)
        final_color = discord.Color.green()
    elif is_player_bj and is_dealer_bj:
        result_text = f"➖ It's a push! Both have Blackjack."
        winnings = game.bet
        final_color = discord.Color.light_grey()
    elif dealer_value > 21:
        result_text = f"✅ Dealer busted with {dealer_value}! You win."
        winnings = game.bet * 2
        final_color = discord.Color.green()
    elif dealer_value > player_value:
        result_text = f"😭 Dealer wins with {dealer_value}."
        winnings = 0
        final_color = discord.Color.red()

    # --- THIS IS THE FIX ---
    # The line was comparing player_value to itself. It is now correctly comparing to dealer_value.
    elif player_value > dealer_value:
        result_text = f"✅ You win with {player_value}!"
        winnings = game.bet * 2
        final_color = discord.Color.green()
    # --- END OF FIX ---

    else:  # Push
        result_text = f"➖ It's a push with {player_value}."
        winnings = game.bet
        final_color = discord.Color.light_grey()

    await modify_coin_adjustment(game.player.id, winnings)

    net_change_for_session = winnings - game.bet

    game.session_winnings = winnings
    game.session_net += net_change_for_session

    final_text = custom_result_text if custom_result_text else result_text

    embed = await create_game_embed(game, final_text, color=final_color)
    await game.message.edit(embed=embed, view=PostHandView(game))


@bot.command(name="bj", aliases=["blackjack"])
async def blackjack(ctx, amount: str):
    """
    Play a game of Blackjack against the dealer.
    Usage: !bj <amount> or !bj <all>
    """
    player = ctx.author

    # REMOVED: The check for an existing game is now gone.
    # if player.id in active_blackjack_games:
    #     await ctx.send("You already have a Blackjack game in progress!", ephemeral=True)
    #     return

    player_balance = await get_effective_balance(player.id)
    bet_amount = player_balance if amount.lower() == 'all' else int(amount)

    if amount.lower() == 'all':
        bet_amount = player_balance
    else:
        try:
            bet_amount = int(amount)
        except ValueError:
            await ctx.send("Please provide a valid number or 'all' for your bet.", ephemeral=True)
            return

    if bet_amount <= 0:
        await ctx.send("Your bet must be a positive amount.", ephemeral=True)
        return

    if player_balance < bet_amount:
        await ctx.send(
            f"You don't have enough coins! Your balance is {player_balance:,} <:wbcoin:1398780929664745652>.",
            ephemeral=True)
        return

    game = BlackjackGame(player, bet_amount)

    await modify_coin_adjustment(player.id, -bet_amount)
    game.initial_deal()

    balance_after_bet = await get_effective_balance(player.id)

    view = ActionView(game, balance_after_bet)
    embed = await create_game_embed(game, "Your turn! What's your move?")
    game_message = await ctx.send(embed=embed, view=view)
    game.message = game_message
    active_blackjack_games[game_message.id] = game

    if calculate_hand_value(game.player_hand) == 21:
        await view.disable_all_buttons()
        game.status = "hand_over";
        await handle_hand_end(game)


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
        color=0x206694  # A dark, techy color
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
        title="<:wbcoin:1398780929664745652> BANK PROFILE",
        color=0x00FFFF  # A bright, neon "cyberpunk" color
    )

    # Use the target's avatar and name in the author field for personalization.
    final_embed.set_author(name=f"{target_user.display_name}'s Balance Information",
                           icon_url=target_user.display_avatar.url)

    # Add the breakdown field for more detail. The ">" creates a nice blockquote effect.
    final_embed.add_field(
        name="EARNINGS:",
        value=f"> Stat-Based Earnings: `{stats_balance:,}`\n"
              f"> Gambling Net Profit/Loss: `{gambling_adjustment:,}`",
        inline=False
    )

    # The main event: the total balance, formatted to stand out.
    final_embed.add_field(
        name="CURRENT BALANCE:",
        value=f"<:wbcoin:1398780929664745652> `{total_balance:,}`",  # "##" makes the text larger
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


def format_timedelta(td: timedelta) -> str:
    """Formats a timedelta object into the largest single unit of time (e.g., '9 hours', '5 minutes')."""
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "less than a minute"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

    return "less than a minute"


@bot.command(name="daily")
async def daily(ctx: commands.Context):
    """Claims your daily coin reward, with a bonus for consecutive days."""
    user = ctx.author
    today = datetime.utcnow().date()

    streak_loss_info = None

    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute("SELECT last_claim_date, streak FROM daily_claims WHERE user_id = ?", (user.id,))
        claim_data = await cursor.fetchone()

        if claim_data and datetime.fromisoformat(claim_data[0]).date() == today:
            tomorrow_utc = datetime.utcnow() + timedelta(days=1)
            next_claim_time = tomorrow_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            time_until_next = next_claim_time - datetime.utcnow()

            embed = discord.Embed(
                title=f"{user.display_name}'s Daily Coins",
                description="You have already claimed your daily reward.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Next Daily", value=f"in {format_timedelta(time_until_next)}")
            await ctx.send(embed=embed)
            return

        base_reward = BASE_DAILY_REWARD
        streak_bonus = 0
        current_streak = 0

        if claim_data is None:
            current_streak = 1
        else:
            last_claim_date = datetime.fromisoformat(claim_data[0]).date()
            saved_streak = claim_data[1]

            if (today - last_claim_date).days == 1:
                current_streak = saved_streak + 1
            else:
                streak_loss_info = {
                    "previous_streak": saved_streak,
                    "days_missed": (today - last_claim_date).days
                }
                current_streak = 1

        if current_streak > 1:
            total_reward = math.floor(base_reward * (DAILY_STREAK_MULTIPLIER ** (current_streak - 1)))
            streak_bonus = total_reward - base_reward
        else:
            total_reward = base_reward

        await modify_coin_adjustment(user.id, total_reward)
        await db.execute("""
            INSERT INTO daily_claims (user_id, last_claim_date, streak) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_claim_date = excluded.last_claim_date, streak = excluded.streak
        """, (user.id, today.isoformat(), current_streak))
        await db.commit()

        tomorrow_utc = datetime.utcnow() + timedelta(days=1)
        next_claim_time = tomorrow_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_next = next_claim_time - datetime.utcnow()

        main_embed_color = discord.Color.green() if not streak_loss_info else discord.Color.light_grey()

        embed = discord.Embed(
            title=f"{user.display_name}'s Daily Coins",
            description=f"> {total_reward:,} <:wbcoin:1398780929664745652> was placed in your wallet!",
            color=main_embed_color
        )

        # --- ✅ THE PERFECT 2x2 GRID SOLUTION ---
        # We manually build two text columns and place them in two inline fields.

        left_column = (
            f"**Base**\n{base_reward:,} <:wbcoin:1398780929664745652>\n\n"
            f"**Next Daily**\n`In {format_timedelta(time_until_next)}`"
        )

        right_column = (
            f"**Streak Bonus**\n{streak_bonus:,} <:wbcoin:1398780929664745652>\n\n"
            f"**Streak**\n{current_streak} 🔥"
        )

        # Add the two manually constructed columns as inline fields.
        # We use an invisible character for the 'name' to keep it clean.
        embed.add_field(name= '', value=left_column, inline=True)
        embed.add_field(name='', value=right_column, inline=True)

        main_message = await ctx.send(embed=embed)

        # --- ✅ SEND THE SECOND EMBED IF THE STREAK WAS LOST ---
        if streak_loss_info:
            streak_lost_embed = discord.Embed(
                title="💔 Streak Lost!",
                description="A daily streak requires claiming once every calendar day (UTC).",
                color=discord.Color.dark_red()
            )
            streak_lost_embed.add_field(name="Last Claim", value=f"{streak_loss_info['days_missed']} days ago",
                                        inline=True)
            streak_lost_embed.add_field(name="Streak Lost", value=f"{streak_loss_info['previous_streak']} days",
                                        inline=True)
            streak_lost_embed.set_footer(text="Don't worry, a new streak has already begun!")

            # We reply to the original message to keep the conversation threaded
            await main_message.reply(embed=streak_lost_embed)


# wordbombmini
@tasks.loop(hours=6)  # Refresh the prompt cache every 6 hours to be safe
async def refresh_prompt_cache():
    """
    Periodically fetches prompts from the new API, handling rate limits and 502 errors.
    """
    global VALID_PROMPTS
    if not api_session:
        print("[ERROR] API session not ready. Skipping prompt fetch.")
        return

    print("[INFO] Starting periodic prompt cache refresh from new API...")

    # Your specified fetch plan: lengths 3 & 4, with max counts of 125, 350, 500
    fetch_params = [
        (3, 125), (3, 400), (4, 600)
    ]

    temp_prompts = {3: set(), 4: set()}

    try:
        for length, max_solves in fetch_params:
            url = f"{WORDBOMB_API_BASE}/syllables/at-most/{LOCALE_FOR_PROMPTS}/{max_solves}?slength={length}"

            # Retry logic for 502 errors
            for attempt in range(3):
                async with api_session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for syllable in data.get("syllables", []):
                            temp_prompts[length].add((syllable['s'].lower(), syllable['c']))
                        print(f"[INFO] Successfully fetched {len(data.get('syllables', []))} prompts for (len={length}, max={max_solves})")
                        break # Success, exit retry loop

                    elif response.status == 502:
                        print(f"[WARN] API returned 502 (Bad Gateway). Retrying in 15 seconds... (Attempt {attempt + 1}/3)")
                        await asyncio.sleep(15)
                        continue # Next attempt

                    else:
                        print(f"[WARN] API call failed for (len={length}, max={max_solves}) with status: {response.status}")
                        break # Unhandled error, stop retrying for this URL

            # CRITICAL RATE LIMITING: Wait 21 seconds (1/3 of a minute)
            print("[INFO] Waiting 1 seconds to respect rate limit...")
            await asyncio.sleep(1)

        new_valid_prompts = {
            length: list(prompts)
            for length, prompts in temp_prompts.items() if prompts
        }

        for length in new_valid_prompts:
            new_valid_prompts[length].sort(key=lambda x: x[1], reverse=True)

        VALID_PROMPTS = new_valid_prompts
        total = sum(len(p) for p in VALID_PROMPTS.values())
        print(f"[SUCCESS] Prompt cache refreshed. Loaded {total} unique prompts.")

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during prompt fetching: {e}")

@refresh_prompt_cache.before_loop
async def before_refresh_cache():
    await bot.wait_until_ready()


async def is_word_valid_api(word: str) -> bool:
    """Checks if a word exists in any language via the new /word/locales/{word} endpoint."""
    if not api_session:
        return False
        
    url = f"{WORDBOMB_API_BASE}/word/locales/{word}"
    try:
        async with api_session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return len(data.get("locales", [])) > 0
            return False
    except Exception as e:
        print(f"[ERROR] An error occurred during word validation for '{word}': {e}")
        return False

def normalize_word(word: str) -> str:
    """Normalizes a word for validation: lowercase, NFKD unicode, strips diacritics."""
    word = word.lower().strip()
    # Normalize unicode characters (e.g., é -> e)
    nfkd_form = unicodedata.normalize('NFKD', word)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


async def fetch_practice_prompts(sub_count: int) -> list:
    """
    Finds practice prompts by locally filtering the main cache to avoid extra API calls.
    """
    print(f"[INFO] Searching local cache for practice prompts with sub_count ~{sub_count}")
    
    # Defines "around" as +/- 40% of the target count
    tolerance = 0.40 
    min_count = sub_count * (1 - tolerance)
    max_count = sub_count * (1 + tolerance)
    
    all_cached_prompts = [p for prompts_list in VALID_PROMPTS.values() for p in prompts_list]
    
    suitable_prompts = [
        (prompt_str, count) for prompt_str, count in all_cached_prompts if min_count <= count <= max_count
    ]
    
    if not suitable_prompts:
        print(f"[WARN] No cached prompts found between {int(min_count)} and {int(max_count)} solves.")
        return []

    random.shuffle(suitable_prompts)
    print(f"[INFO] Found {len(suitable_prompts)} suitable practice prompts in the cache.")
    return suitable_prompts


@tasks.loop(hours=1)
async def check_and_delete_old_threads():
    """Periodically checks for practice threads that are older than 24 hours and deletes them."""
    print("[INFO] Running periodic check for old practice threads...")
    # 24 hours ago from now
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

    threads_to_delete = []
    async with aiosqlite.connect("server_data.db") as db:
        # Find all practice rooms where the last prompt was started before the cutoff time
        cursor = await db.execute(
            "SELECT channel_id FROM word_minigame_active WHERE is_practice = 1 AND start_timestamp < ?",
            (cutoff_time.isoformat(),)
        )
        threads_to_delete = await cursor.fetchall()

        if threads_to_delete:
            # Get just the IDs
            thread_ids = [row[0] for row in threads_to_delete]
            # Create a placeholder string for the query, e.g., (?, ?, ?)
            placeholders = ', '.join('?' for _ in thread_ids)

            # Clean up the database records for all expired threads in one go
            await db.execute(f"DELETE FROM word_minigame_active WHERE channel_id IN ({placeholders})", thread_ids)
            await db.commit()
            print(f"[INFO] Cleaned up {len(thread_ids)} expired practice rooms from the database.")

    # Now, delete the actual Discord threads
    for thread_id_tuple in threads_to_delete:
        thread_id = thread_id_tuple[0]
        try:
            # Fetch the thread object. It might already be deleted.
            thread = bot.get_channel(thread_id) or await bot.fetch_channel(thread_id)
            if thread:
                print(f"[INFO] Deleting expired practice thread: {thread.name} ({thread.id})")
                await thread.delete()
        except discord.NotFound:
            # The thread was already deleted, which is fine.
            print(f"[INFO] Tried to delete thread {thread_id}, but it was already gone.")
        except discord.Forbidden:
            print(f"[WARN] Lacked permissions to delete expired thread {thread_id}.")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred while deleting thread {thread_id}: {e}")


@check_and_delete_old_threads.before_loop
async def before_check_threads():
    await bot.wait_until_ready()

PROMPT_EMOJI_MAP = {
    'a': '<:key_A:1409612462227062824>', 'b': '<:key_B:1409612493784875070>',
    'c': '<:key_C:1409612512583749672>', 'd': '<:key_D:1409612531990794394>',
    'e': '<:key_E:1409612547870429317>', 'f': '<:key_F:1409612565100888155>',
    'g': '<:key_G:1409612583849295924>', 'h': '<:key_H:1409612622692618311>',
    'i': '<:key_I:1409612660525367449>', 'j': '<:key_J:1409612676488761465>',
    'k': '<:key_K:1409612691517210785>', 'l': '<:key_L:1409612709116379287>',
    'm': '<:key_M:1409612725843263698>', 'n': '<:key_N:1409612739684339732>',
    'o': '<:key_O:1409612752041021550>', 'p': '<:key_P:1409612768042025082>',
    'q': '<:key_Q:1409612783338918058>', 'r': '<:key_R:1409612799075680287>',
    's': '<:key_S:1409612813814464533>', 't': '<:key_T:1409612827525644320>',
    'u': '<:key_U:1409612841538945025>', 'v': '<:key_V:1409612853685518469>',
    'w': '<:key_W:1409612867879309312>', 'x': '<:key_X:1409612881623777341>',
    'y': '<:key_Y:1409612895054069760>', 'z': '<:key_Z:1409612925345206374>',
    "'": '<:key_apostrophe:1409612478127669439>',
    '-': '<:key_hyphen:1409612639285547018>'
}

# --- White Emojis for the Solved Word ---
SOLVE_EMOJI_MAP = {
    'a': '<:key_A2:1409612470464807014>', 'b': '<:key_B2:1409612503734030508>',
    'c': '<:key_C2:1409612522163535932>', 'd': '<:key_D2:1409612538781499523>',
    'e': '<:key_E2:1409612556343181463>', 'f': '<:key_F2:1409612573250289716>',
    'g': '<:key_G2:1409612610449576107>', 'h': '<:key_H2:1409612630875701383>',
    'i': '<:key_I2:1409612668805058752>', 'j': '<:key_J2:1409612683325608046>',
    'k': '<:key_K2:1409612706230702131>', 'l': '<:key_L2:1409612716036853991>',
    'm': '<:key_M2:1409612732138918000>', 'n': '<:key_N2:1409612746051551363>',
    'o': '<:key_O2:1409612760202874973>', 'p': '<:key_P2:1409612774518030416>',
    'q': '<:key_Q2:1409612790934671461>', 'r': '<:key_R2:1409612806008868934>',
    's': '<:key_S2:1409612820227686561>', 't': '<:key_T2:1409612834580725921>',
    'u': '<:key_U2:1409612847679410307>', 'v': '<:key_V2:1409612860270841936>',
    'w': '<:key_W2:1409612875219075162>', 'x': '<:key_X2:1409612887953244231>',
    'y': '<:key_Y2:1409612904411693126>', 'z': '<:key_Z2:1409612933431824434>',
    "'": '<:key_apostrophe2:1409612486541312111>',
    '-': '<:key_hyphen2:1409612647074234408>'
}

TRASH_TALK_LINES = (
    "Too slow, {mention}, the prompt was already solved bro. Nice word though.",
    "{mention} nice try buddy. Prompt was already solved though :wilted_rose:."
)

_last_solved_prompt_info = {}


def format_word_emojis(word: str, prompt: str = None) -> str:
    """
    Converts a word into a sequence of custom emojis with advanced highlighting.

    - If only 'word' is provided, it uses the blue PROMPT_EMOJI_MAP.
    - If 'word' and 'prompt' are provided, it uses the white SOLVE_EMOJI_MAP
      and highlights the first occurrence of the prompt in blue.
    """
    word_lower = word.lower()

    # --- SCENARIO 1: Just creating the blue prompt ---
    if prompt is None:
        return "".join(PROMPT_EMOJI_MAP.get(char, char) for char in word_lower)

    # --- SCENARIO 2: Creating the highlighted solved word ---
    prompt_lower = prompt.lower()
    start_index = word_lower.find(prompt_lower)

    # This should always find a match, but we check just in case.
    if start_index == -1:
        # Fallback if the prompt isn't found (shouldn't happen with valid solves)
        return "".join(SOLVE_EMOJI_MAP.get(char, char) for char in word_lower)

    end_index = start_index + len(prompt_lower)
    emoji_string = []

    # Part 1: Before the prompt (white)
    for char in word_lower[:start_index]:
        emoji_string.append(SOLVE_EMOJI_MAP.get(char, char))

    # Part 2: The prompt itself (blue)
    for char in word_lower[start_index:end_index]:
        emoji_string.append(PROMPT_EMOJI_MAP.get(char, char))

    # Part 3: After the prompt (white)
    for char in word_lower[end_index:]:
        emoji_string.append(SOLVE_EMOJI_MAP.get(char, char))

    return "".join(emoji_string)

@bot.event
async def on_raw_message_delete(payload):
    """Handles the case where a moderator accidentally deletes the active prompt message."""
    # Check if the deleted message was in our game channel
    if payload.channel_id != WORD_GAME_CHANNEL_ID:
        return

    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute(
            "SELECT current_prompt FROM word_minigame_active WHERE message_id = ?",
            (payload.message_id,)
        )
        game_data = await cursor.fetchone()

        if game_data:
            print(f"[WARN] Word game prompt message {payload.message_id} was deleted. Re-posting...")
            # If a game was associated with that message, start a new round.
            # This effectively re-posts the prompt and updates the message_id.
            channel = bot.get_channel(WORD_GAME_CHANNEL_ID)
            if channel:
                # To prevent a dead prompt, we'll just start the next round immediately.
                await start_new_word_game_round(channel)


def get_new_prompt(turn_in_round: int) -> tuple | None:
    """
    Selects a prompt based on the current turn, with a randomness factor.
    """
    if not VALID_PROMPTS: return None

    # --- Step 1: Calculate the core target difficulty (same as before) ---
    progress = (turn_in_round - 1) / (ROUND_LENGTH - 1)
    difficulty_drop = ROUND_START_DIFFICULTY - ROUND_END_DIFFICULTY
    target_count = ROUND_START_DIFFICULTY - (progress * difficulty_drop)

    # --- Step 2: NEW - Define a "randomness window" around the target ---
    # This creates a +/- 15% window. e.g., if target is 300, it looks for prompts between 255-345.
    randomness_factor = 0.15
    lower_bound = target_count * (1 - randomness_factor)
    upper_bound = target_count * (1 + randomness_factor)

    # --- Step 3: Find all suitable prompts within this window ---
    all_prompts = [p for prompts_list in VALID_PROMPTS.values() for p in prompts_list]

    candidate_prompts = [
        (prompt, match_count) for prompt, match_count in all_prompts
        if lower_bound <= match_count <= upper_bound and prompt not in _recent_prompts
    ]

    # --- Step 4: Pick a random prompt from the candidates ---
    if candidate_prompts:
        # If we found fresh prompts in the window, pick one randomly.
        chosen_prompt = random.choice(candidate_prompts)
        _recent_prompts.append(chosen_prompt[0])
        return chosen_prompt
    else:
        # Fallback: If no fresh prompts were in the window (e.g., they were all recent),
        # widen the search and pick the first available one to avoid errors.
        print(
            f"[WARN] No fresh prompts found in window [{int(lower_bound)}-{int(upper_bound)}]. Picking best available.")
        # We find the single best match closest to our target.
        # The `min` function's `key` finds the prompt with the smallest absolute difference from our target.
        best_fallback = min(all_prompts, key=lambda p: abs(p[1] - target_count))
        _recent_prompts.append(best_fallback[0])
        return best_fallback


def create_word_game_embed(prompt: str, match_count: int, start_time: datetime) -> discord.Embed:
    """Creates the standard embed for the word mini-game prompt."""
    embed = discord.Embed(
        # --- MODIFIED LINE ---
        title=f"<:logo:1409319111632224268> Prompt: {format_word_emojis(prompt)}",
        description="Be the first to type a valid word in any \nlanguage containing the substring above!",
        color=discord.Color.purple()
    )

    embed.add_field(name="Dictionary Matches", value=f"This prompt is sub `{match_count:,}`.", inline=False)

    embed.set_footer(text="Good luck!")
    embed.timestamp = start_time
    return embed


async def start_new_word_game_round(channel: discord.TextChannel | discord.Thread, is_practice: bool = False, sub_count: int = None, creator_id: int = None, new_round_announcement: str = None):
    """Generates a new prompt, now also storing the creator's ID for practice rooms."""

    if new_round_announcement:
        await channel.send(new_round_announcement)
        await asyncio.sleep(2)

    prompt, match_count = (None, 0)

    if is_practice:
        prompt_list = await fetch_practice_prompts(sub_count)
        if prompt_list:
            prompt, match_count = random.choice(prompt_list)
    else:
        # Public games now use the round state
        async with aiosqlite.connect("server_data.db") as db:
            cursor = await db.execute("SELECT turn_in_round FROM word_minigame_round_state WHERE channel_id = ?",
                                      (channel.id,))
            round_data = await cursor.fetchone()
            current_turn = round_data[0] if round_data else 1

        result = get_new_prompt(current_turn)
        if result: prompt, match_count = result

    if not prompt:
        await channel.send("`[ERROR] Could not find a suitable prompt.`")
        return

    start_time = datetime.now(timezone.utc)
    embed = create_word_game_embed(prompt, match_count, start_time)

    try:
        prompt_message = await channel.send(embed=embed)
    except discord.Forbidden:
        print(f"[ERROR] Cannot send messages in {channel.name}.")
        return

    async with aiosqlite.connect("server_data.db") as db:
        await db.execute("""
            INSERT OR REPLACE INTO word_minigame_active 
            (channel_id, current_prompt, message_id, start_timestamp, is_practice, sub_count, creator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (channel.id, prompt, prompt_message.id, start_time.isoformat(), int(is_practice), sub_count, creator_id))
        await db.commit()

    if is_practice:
        print(f"[INFO] New practice round started in thread '{channel.name}' with prompt '{prompt}'.")
    else:
        print(f"[INFO] New public game round started in #{channel.name} with prompt '{prompt}'.")

@bot.command(name="createroom")
async def createroom(ctx: commands.Context, sub_count: int = None):
    """Creates a private practice thread for the WordBomb mini-game."""
    if ctx.channel.id != PRACTICE_ROOM_COMMAND_CHANNEL_ID:
        return

    # --- Check for existing active room (this logic is correct and unchanged) ---
    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute(
            "SELECT channel_id FROM word_minigame_active WHERE creator_id = ? AND is_practice = 1",
            (ctx.author.id,)
        )
        existing_room = await cursor.fetchone()
        if existing_room:
            thread_id = existing_room[0]
            return await ctx.send(f"❌ {ctx.author.mention}, you already have an active practice room here: <#{thread_id}>. Please `!close` it before creating a new one.")

    if sub_count is None:
        return await ctx.send("Please provide a sub count difficulty (e.g., `!createroom 100`).")
    if not 10 <= sub_count <= 2000:
        return await ctx.send("Please choose a sub count between 10 and 2,000.")

    feedback_msg = await ctx.send(f"➡️ {ctx.author.mention}, fetching prompts and creating your private room...")

    prompts = await fetch_practice_prompts(sub_count)
    if not prompts:
        return await feedback_msg.edit(content=f"❌ {ctx.author.mention}, I couldn't find any prompts with that difficulty.")

    try:
        thread_type = discord.ChannelType.private_thread

        thread = await ctx.channel.create_thread(
            name=f"🔵 Practice Room for {ctx.author.display_name}",
            type=thread_type
        )

        await thread.add_user(ctx.author)

        await feedback_msg.edit(content=f"✅ {ctx.author.mention}, your private practice room has been created: {thread.mention}")

        welcome_embed = discord.Embed(
            title=f"Welcome to your Practice Room!",
            description=(
                f"This is a private space for you to practice the Word Bomb game with prompts around a **{sub_count}** sub count.\n\n"
                "**RULES:**\n"
                "• Solves here do **not** count for leaderboards, streaks, or coins.\n"
                "• The game works exactly like the public version.\n"
                f"• This thread will automatically close after 24 hours of inactivity. You can also close it manually with `!close`."
            ),
            color=discord.Color.blue()
        )
        await thread.send(embed=welcome_embed)
        # Start the first round in the new thread
        await start_new_word_game_round(
            thread,
            is_practice=True,
            sub_count=sub_count,
            creator_id=ctx.author.id  # This was the missing piece
        )

    except Exception as e:
        print(f"[ERROR] Failed to create practice thread: {e}")
        await feedback_msg.edit(content=f"❌ {ctx.author.mention}, an error occurred while trying to create your room.")


@bot.command(name="close")
async def close(ctx: commands.Context):
    """Closes an active practice room thread."""
    if not isinstance(ctx.channel, discord.Thread):
        return # Ignore if not in a thread

    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute("SELECT is_practice FROM word_minigame_active WHERE channel_id = ?", (ctx.channel.id,))
        game_data = await cursor.fetchone()

        if game_data and game_data[0] == 1: # Check if it's a practice room
            await ctx.send("✅ This practice room will now be closed.")
            await db.execute("DELETE FROM word_minigame_active WHERE channel_id = ?", (ctx.channel.id,))
            await db.commit()
            await asyncio.sleep(0.5)
            await ctx.channel.delete()


def is_specific_user(user_id: int):
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == user_id
    return commands.check(predicate)


@bot.command(name="startwordgame")
async def start_word_game(ctx: commands.Context):
    """(Admin-only) Starts the first round of the word mini-game."""
    DEVELOPER_IDS = {265196052192165888, 849827666064048178}
    if ctx.author.id not in DEVELOPER_IDS:
        return await ctx.send("🚫 You do not have permission to use this command.")

    if ctx.channel.id != WORD_GAME_CHANNEL_ID:
        return await ctx.send(f"This command can only be used in the designated game channel.")

    if not VALID_PROMPTS:
        # --- MODIFIED ERROR MESSAGE ---
        return await ctx.send(
            "❌ **Cannot start game:** No valid prompts were loaded on startup.\n"
            "Please check the console logs for API connection errors."
        )

    await ctx.send("✅ Starting the first round of the word game...")
    await start_new_word_game_round(ctx.channel)


@tasks.loop(minutes=6)
async def update_status_panel():
    """Fetches API status and updates the persistent embed."""
    global _status_panel_message
    if not _status_panel_message:
        print("[ERROR] Status panel message object is not set. Cannot update.")
        return

    print("[INFO] Updating status panel...")
    
    # Define a helper map for emojis and colors
    status_map = {
        "operational": {"emoji": "🟢", "color": discord.Color.green()},
        "degraded_performance": {"emoji": "🟡", "color": discord.Color.gold()},
        "partial_outage": {"emoji": "🟠", "color": discord.Color.orange()},
        "major_outage": {"emoji": "🔴", "color": discord.Color.red()},
    }
    default_status = {"emoji": "⚪", "color": discord.Color.light_grey()}

    try:
        async with api_session.get(STATUS_API_URL) as response:
            if response.status == 200:
                data = await response.json()
                
                # --- Build the Embed from API Data ---
                overall_status = data.get("overall", "unknown").lower()
                status_info = status_map.get(overall_status, default_status)
                
                embed = discord.Embed(
                    title=f"{status_info['emoji']} Word Bomb API Status",
                    description=f"Overall status: **{overall_status.replace('_', ' ').title()}**",
                    color=status_info['color']
                )

                for service in data.get("services", []):
                    service_status = service.get("status", "unknown").lower()
                    service_info = status_map.get(service_status, default_status)
                    
                    value = (
                        f"{service_info['emoji']} {service_status.replace('_', ' ').title()}\n"
                        f"**Response Time:** `{service.get('responseTime', 'N/A')}ms`"
                    )
                    embed.add_field(name=service.get("name", "Unknown Service"), value=value, inline=True)

                # Parse and set the timestamp
                last_updated_str = data.get("lastUpdated", "").replace("Z", "+00:00")
                if last_updated_str:
                    embed.timestamp = datetime.fromisoformat(last_updated_str)
                    
            else:
                # Handle API errors
                embed = discord.Embed(
                    title="🔴 API Status Unknown",
                    description=f"Failed to fetch status from the API. Received HTTP status code `{response.status}`.",
                    color=discord.Color.dark_red(),
                    timestamp=datetime.now(timezone.utc)
                )

    except aiohttp.ClientConnectorError as e:
        print(f"[ERROR] Connection error while fetching API status: {e}")
        embed = discord.Embed(
            title="🔴 API Status Unknown",
            description="Could not connect to the Word Bomb API. The service may be offline.",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred in update_status_panel: {e}")
        return # Don't update the message on an unexpected error

    try:
        await _status_panel_message.edit(embed=embed)
        print("[SUCCESS] Status panel updated.")
    except discord.NotFound:
        print("[ERROR] The status panel message was deleted. It will be recreated on next bot restart.")
        _status_panel_message = None # Clear the message object
        update_status_panel.stop() # Stop the loop to prevent spamming errors
    except discord.Forbidden:
        print(f"[ERROR] Lacking permissions to edit messages in the status panel channel.")
        update_status_panel.stop()

@update_status_panel.before_loop
async def before_update_status_panel():
    await bot.wait_until_ready()


class RoleButtonView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # --- BUTTON 1: Game Updates (Unchanged logic, just a name change for clarity) ---
    @ui.button(label="Game Updates", style=discord.ButtonStyle.secondary, emoji="📢", custom_id="game_updates_role_btn")
    async def game_updates_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(GAME_UPDATES_ROLE_ID)
        if not role:
            await interaction.followup.send("Error: The 'Game Updates' role could not be found.", ephemeral=True)
            return

        user_has_role = any(r.id == GAME_UPDATES_ROLE_ID for r in interaction.user.roles)
        try:
            if user_has_role:
                await interaction.user.remove_roles(role)
                await interaction.followup.send("✅ You will no longer be notified of game updates.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send("✅ You will now be notified of game updates!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Error: I don't have permission to manage the 'Game Updates' role.", ephemeral=True)

    # --- NEW BUTTON 2: Dictionary Updates ---
    @ui.button(label="Dictionary Updates", style=discord.ButtonStyle.secondary, emoji="📖", custom_id="dict_updates_role_btn")
    async def dictionary_updates_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        role = interaction.guild.get_role(DICTIONARY_UPDATES_ROLE_ID)
        if not role:
            await interaction.followup.send("Error: The 'Dictionary Updates' role could not be found.", ephemeral=True)
            return

        user_has_role = any(r.id == DICTIONARY_UPDATES_ROLE_ID for r in interaction.user.roles)
        try:
            if user_has_role:
                await interaction.user.remove_roles(role)
                await interaction.followup.send("✅ You will no longer be notified of dictionary updates.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send("✅ You will now be notified of dictionary updates!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Error: I don't have permission to manage the 'Dictionary Updates' role.", ephemeral=True)

@bot.command(name="setup_role_button")
async def setup_role_button(ctx: commands.Context):
    """(Admin-only) Posts the persistent role-assignment message."""
    DEVELOPER_IDS = {265196052192165888, 849827666064048178}
    if ctx.author.id not in DEVELOPER_IDS:
        return await ctx.send("🚫 You do not have permission to use this command.")

    target_channel = bot.get_channel(ROLE_BUTTON_CHANNEL_ID)
    if not target_channel:
        return await ctx.send(f"❌ Error: Could not find the channel with ID `{ROLE_BUTTON_CHANNEL_ID}`.")

    # --- UPDATED EMBED TEXT ---
    embed = discord.Embed(
        title="📢 Notification Roles",
        description=(
            "Click the buttons below to subscribe to notifications for topics that interest you.\n\n"
            "• **Game Updates:** Get pinged for new features and updates to our game.\n"
            "• **Dictionary Updates:** Get pinged when the server updates to the latest dictionary version."
        ),
        color=discord.Color.blue()
    )

    await target_channel.send(embed=embed, view=RoleButtonView())
    await ctx.send(f"✅ Role button message has been sent to {target_channel.mention}.")


async def generate_user_chart(user: discord.Member) -> io.BytesIO | None:
    """
    Fetches a user's message data for the last 7 days and generates a bar chart.
    Returns an in-memory image file or None if no data is available.
    """
    today = datetime.utcnow().date()
    # --- THE FIX: Calculate a rolling 7-day period ---
    # The start date is now simply 6 days before today.
    start_date = today - timedelta(days=6)
    
    # Create a list of the last 7 dates, ending with today.
    date_range = [start_date + timedelta(days=i) for i in range(7)]
    
    # Fetch data from the database for this new date range
    user_data = {}
    async with aiosqlite.connect("server_data.db") as db:
        cursor = await db.execute(
            "SELECT message_date, count FROM daily_message_history WHERE user_id = ? AND message_date >= ?",
            (user.id, start_date.strftime("%Y-%m-%d"))
        )
        async for row in cursor:
            user_data[row[0]] = row[1]
            
    # --- THE FIX: Generate day labels dynamically ---
    # This creates labels like ['Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu']
    day_labels = [date.strftime("%a") for date in date_range]
    message_counts = [user_data.get(date.strftime("%Y-%m-%d"), 0) for date in date_range]

    if sum(message_counts) == 0:
        return None

    # --- Chart Generation (this part remains the same) ---
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(day_labels, message_counts, color='#5865F2')
    
    # --- THE FIX: Update the title to be more accurate ---
    ax.set_title(f"Last 7 Days of Message Activity for {user.display_name}", fontsize=16, pad=20)
    ax.set_ylabel("Messages Sent", fontsize=12)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='x', which='major', labelsize=12, length=0)
    ax.tick_params(axis='y', which='major', labelsize=10, length=0)
    ax.yaxis.grid(True, linestyle='--', linewidth=0.5, color='#4E5058')
    ax.set_ylim(0, max(message_counts) * 1.15)

    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width() / 2.0, height, f'{height}', ha='center', va='bottom', fontsize=11)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    
    return buf

@bot.command(name="chart")
async def chart(ctx: commands.Context, member: discord.Member = None):
    """Generates a bar chart of a user's message activity for the last 7 days."""
    target_user = member or ctx.author

    if target_user.bot:
        return await ctx.send("Bots don't send messages to chart!")

    processing_msg = await ctx.send(f"📈 Generating last 7 days of activity for **{target_user.display_name}**...")

    chart_buffer = await generate_user_chart(target_user)

    if chart_buffer:
        file = discord.File(chart_buffer, filename=f"{target_user.id}_chart.png")
        
        # --- THE FIX: Update the embed description ---
        embed = discord.Embed(
            title=f"Message Chart for {target_user.display_name}",
            description="Showing messages sent over the last 7 days.",
            color=discord.Color.blue()
        )
        embed.set_image(url=f"attachment://{target_user.id}_chart.png")
        embed.set_footer(text=f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        await processing_msg.edit(content=None, embed=embed, attachments=[file])
    else:
        await processing_msg.edit(content=f"📊 No message activity found for **{target_user.display_name}** in the last 7 days.")

async def update_member_s_roles(member: discord.Member):
    """
    The core logic hub for managing server tag roles with a specific exception
    for Language Moderators who are also Server Boosters.
    """
    if member.guild.id != TAG_CHECK_GUILD_ID or member.bot:
        return

    try:
        # Step 1: Determine the user's eligibility for an S-role.
        
        # Check for the specific role combination first (this is fast and local).
        is_booster = discord.utils.get(member.roles, name="Server Booster") is not None
        is_language_mod = discord.utils.get(member.roles, name="Language Moderator") is not None
        booster_lm_exception = is_booster and is_language_mod

        # Now, check if they have the server tag active via an API call.
        user_data = await bot.http.get_user(member.id)
        primary_guild_info = user_data.get('primary_guild')
        has_server_tag = False
        if primary_guild_info:
            if primary_guild_info.get('identity_enabled') and primary_guild_info.get('identity_guild_id') == str(TAG_CHECK_GUILD_ID):
                has_server_tag = True
        
        # A member is eligible if they have the tag OR meet the specific booster+LM exception.
        is_eligible = has_server_tag or booster_lm_exception

        # Step 2: Get all S-Roles the member CURRENTLY has.
        current_s_roles = [role for role in member.roles if role.name in ALL_S_ROLES]

        # Step 3: Find the highest qualifying base role they have from our hierarchy.
        target_s_role_name = None
        for base_role_name, s_role_name in S_ROLE_HIERARCHY:
            if discord.utils.get(member.roles, name=base_role_name):
                target_s_role_name = s_role_name
                break # Stop at the first (highest) one found

        # --- Role Reconciliation Logic ---
        
        # CASE A: The user is NOT eligible for any S-role.
        if not is_eligible:
            if current_s_roles: # If they have any S-roles, remove them all.
                reason = "User does not have the tag active and does not meet the booster exception."
                print(f"[S-ROLE] User '{member.name}' is not eligible. Removing {len(current_s_roles)} S-Role(s).")
                await member.remove_roles(*current_s_roles, reason=reason)
            return # Stop here.

        # CASE B: The user IS eligible for an S-role.
        # We now need to ensure they have the correct one and only one.
        target_s_role = discord.utils.get(member.guild.roles, name=target_s_role_name) if target_s_role_name else None

        roles_to_remove = []
        for role in current_s_roles:
            # If the user has an S-role that is NOT their target, mark it for removal.
            if not target_s_role or role.id != target_s_role.id:
                roles_to_remove.append(role)

        if roles_to_remove:
            reason = "Adjusting S-Role based on hierarchy or eligibility change."
            print(f"[S-ROLE] User '{member.name}' hierarchy changed. Removing {len(roles_to_remove)} incorrect S-Role(s).")
            await member.remove_roles(*roles_to_remove, reason=reason)

        if target_s_role and target_s_role not in member.roles:
            reason = "Assigning S-Role for tag or booster+LM eligibility."
            print(f"[S-ROLE] Assigning target S-Role '{target_s_role.name}' to '{member.name}'.")
            await member.add_roles(target_s_role, reason=reason)

    except discord.Forbidden:
        print(f"[ERROR] [S-ROLE] Lacking permissions to manage roles for user '{member.name}'. Check bot's role position.")
    except Exception as e:
        print(f"[ERROR] [S-ROLE] An unexpected error occurred while updating roles for '{member.name}': {e}")


@bot.event
async def on_member_join(member: discord.Member):
    """
    Checks a new member's server tag status when they join the server.
    """
    await update_member_s_roles(member)

# ✅ NEW EVENT HANDLER FOR MEMBER UPDATES (ROLES, PROFILE, ETC.)
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """
    Re-evaluates a member's S-roles whenever their profile or roles change.
    """
    # This check prevents running the logic twice if only insignificant things change
    if before.roles != after.roles or before.display_avatar != after.display_avatar:
         await update_member_s_roles(after)


@bot.group(name="shop", invoke_without_command=True)
async def shop(ctx: commands.Context):
    """Displays the item shop embed. This runs when a user types just '!shop'."""
    # This block runs if the user just typed "!shop" without a subcommand like "buy".
    if ctx.invoked_subcommand is None:
        user_balance = await get_effective_balance(ctx.author.id)

        embed = discord.Embed(
            title="<:wbcoin:1398780929664745652> Item Shop",
            description="Use `!shop buy <item> [amount]` to purchase an item.",
            color=discord.Color.blue()
        )

        # Loop through the items and add a field for each one
        for item_name, data in SHOP_ITEMS.items():
            emoji = f"<:item:{data['emoji_id']}>"
            price = data['price']
            reward = data['reward_text']
            
            embed.add_field(
                name=f"{emoji} {item_name.capitalize()}",
                value=f"**Cost:** {price:,} <:wbcoin:1398780929664745652>\n*Reward: {reward}*",
                inline=True
            )
        
        embed.set_footer(text=f"Your current balance: {user_balance:,} coins")
        await ctx.send(embed=embed)


@shop.command(name="buy")
async def buy(ctx: commands.Context, item_name: str, amount: int = 1):
    """Handles the logic for purchasing an item from the shop."""
    author = ctx.author
    item_name_lower = item_name.lower()

    # --- 1. VALIDATION ---
    if item_name_lower not in SHOP_ITEMS:
        valid_items = ", ".join(SHOP_ITEMS.keys())
        return await ctx.send(f"❌ That's not a valid item. Valid items are: `{valid_items}`")
    
    if amount <= 0:
        return await ctx.send("❌ You must purchase a positive amount.")

    item_data = SHOP_ITEMS[item_name_lower]
    total_cost = item_data["price"] * amount
    
    # --- 2. BALANCE CHECK ---
    user_balance = await get_effective_balance(author.id)
    if user_balance < total_cost:
        return await ctx.send(f"❌ You don't have enough coins! You need **{total_cost:,}** but you only have **{user_balance:,}** <:wbcoin:1398780929664745652>.")

    # --- 3. API CALL (SAFETY FIRST!) ---
    try:
        # ✅ FIX: Prepare both the URL and the JSON payload as required by the API.
        item_api_id = item_data['api_id']
        url = f"{SHOP_API_BASE_URL}/{author.id}/{item_api_id}/{amount}"
        
        # This dictionary will be converted to the JSON body: {"item": "helmet", "count": 1}
        payload = {
            "item": item_api_id,
            "count": amount
        }
        
        print(f"[SHOP] Making API POST request to: {url} with payload: {payload}")

        async with api_session.post(url, json=payload) as response:
            if response.status not in [200, 204]:
                error_text = await response.text()
                print(f"[ERROR] [SHOP] API call failed with status {response.status}: {error_text}")
                raise Exception("API call failed")

        print(f"[SHOP] API call successful for {author.name}.")

    except Exception as e:
        await ctx.send("❌ An error occurred while contacting the game server. Your purchase has been cancelled, and you have not been charged. Please try again later.")
        print(f"[ERROR] [SHOP] An exception occurred during the API call: {e}")
        return

    # --- 4. COIN DEDUCTION ---
    success = await modify_coin_adjustment(author.id, -total_cost)
    if not success:
        await ctx.send("🚨 **CRITICAL ERROR!** We gave you the item(s), but failed to deduct your coins. Please contact a developer.")
        print(f"[CRITICAL] [SHOP] API call succeeded for {author.name} but coin deduction failed!")
        return

    # --- 5. CONFIRMATION MESSAGE ---
    new_balance = user_balance - total_cost
    emoji = f"<:item:{item_data['emoji_id']}>"
    
    embed = discord.Embed(
        title="✅ Purchase Successful!",
        description=f"You successfully purchased **{amount}x {emoji} {item_name.capitalize()}**!",
        color=discord.Color.green()
    )
    embed.add_field(name="Total Cost", value=f"{total_cost:,} <:wbcoin:1398780929664745652>", inline=True)
    embed.add_field(name="New Balance", value=f"{new_balance:,} <:wbcoin:1398780929664745652>", inline=True)
    embed.set_footer(text=f"Thank you for your purchase, {author.display_name}!")
    
    await ctx.send(embed=embed)


#Admin Commands
@bot.command(name="resetstreak")
async def resetstreak(ctx: commands.Context, member: discord.Member = None):
    """
    Modifies a user's daily record to simulate a streak loss on their next claim. (Admin Only)

    If no user is specified, it targets your own record.
    """
    ALLOWED_USER_ID = 849827666064048178

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this command.")

    target_user = member or ctx.author

    async with aiosqlite.connect("server_data.db") as db:
        # First, we need to get the user's current streak to display it
        cursor = await db.execute("SELECT streak FROM daily_claims WHERE user_id = ?", (target_user.id,))
        row = await cursor.fetchone()

        if not row:
            return await ctx.send(f"**{target_user.display_name}** has no daily streak history to modify.")

        streak_to_be_reset = row[0]

        # We set the last claim date to two days ago to guarantee a streak break
        reset_date = (datetime.utcnow() - timedelta(days=2)).date()

        await db.execute(
            "UPDATE daily_claims SET last_claim_date = ? WHERE user_id = ?",
            (reset_date.isoformat(), target_user.id)
        )
        await db.commit()

    # Create a more descriptive confirmation embed
    embed = discord.Embed(
        title="✅ Daily Streak Primed for Reset",
        description=(
            f"The daily claim history for **{target_user.mention}** has been modified. "
            "Their next `!daily` claim will now trigger a natural streak loss."
        ),
        color=discord.Color.orange()
    )
    embed.add_field(name="Admin", value=ctx.author.mention, inline=True)
    embed.add_field(name="Target", value=target_user.mention, inline=True)
    embed.add_field(name="Current Streak (to be lost)", value=f"{streak_to_be_reset} days", inline=False)

    await ctx.send(embed=embed)


@resetstreak.error
async def resetstreak_error(ctx, error):
    """Handles errors for the resetstreak command."""
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(
            f"❌ Could not find the member '{error.argument}'. Please make sure you've tagged a valid user in this server.")

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


@bot.command(name="addstats", aliases=["addpoints"])
async def addstats(ctx: commands.Context, member: discord.Member, category: str, amount: int):
    """
    Adds a specified amount of points to a user in a specific category. (Admin Only)

    Valid Categories: messages, bugs, ideas, voice
    This command does NOT affect coins or trivia. Use !addcoins for coin changes.
    """
    # --- 1. Input Validation ---
    category = category.lower()
    if member.bot:
        return await ctx.send("❌ You cannot modify stats for a bot.")
    if amount <= 0:
        return await ctx.send("❌ The amount to add must be a positive number.")

    ALLOWED_USER_ID = 849827666064048178  # Make sure this is your correct admin ID

    if ctx.author.id != ALLOWED_USER_ID:
        return await ctx.send("🚫 You are not authorized to use this powerful command.")

    # --- 2. Map Category to Database Table and Column ---
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
            # First, get the user's current score for the 'before' part of the confirmation
            cursor = await db.execute(f"SELECT {column_name} FROM {table_name} WHERE user_id = ?", (member.id,))
            row = await cursor.fetchone()
            current_score = row[0] if row else 0

            # This single, robust query will add points for an existing user
            # OR create the user with the specified points if they don't exist.
            await db.execute(f"""
                INSERT INTO {table_name} (user_id, {column_name}) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET {column_name} = {column_name} + excluded.{column_name}
            """, (member.id, amount))
            await db.commit()

            # Get the new score for confirmation
            cursor = await db.execute(f"SELECT {column_name} FROM {table_name} WHERE user_id = ?", (member.id,))
            new_score = (await cursor.fetchone())[0]

    except Exception as e:
        await ctx.send(f"❌ An unexpected database error occurred: {e}")
        print(f"[ERROR] An exception occurred during the addstats command: {e}")
        return

    # --- 4. Confirmation Embed ---
    unit = "seconds" if category == "voice" else "points"
    embed = discord.Embed(
        title="✅ Admin Action: Stats Added",
        description=f"Successfully added points to **{member.display_name}**.",
        color=discord.Color.green()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
    embed.add_field(name="Target User", value=member.mention, inline=False)
    embed.add_field(name="Category", value=f"`{category.capitalize()}`", inline=True)
    embed.add_field(name="Amount Added", value=f"`{amount:,} {unit}`", inline=True)
    embed.add_field(name="Score Update", value=f"`{current_score:,}` ➡️ `{new_score:,}`", inline=False)

    await ctx.send(embed=embed)


@addstats.error
async def addstats_error(ctx, error):
    """Handles errors for the addstats command."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have the required `Administrator` permission to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Incorrect usage. You need to specify a member, a category, and an amount.\n**Example:** `!addstats @User messages 100`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Couldn't find that member or the amount provided was not a valid whole number.")
    else:
        print(f"An unhandled error occurred in the addstats command: {error}")

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