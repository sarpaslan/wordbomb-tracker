import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import aiosqlite
import random
import datetime
import time
import sqlite3
import threading

# Load token
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bug_points (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS idea_points (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggest_points (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS voice_time (
                user_id INTEGER PRIMARY KEY,
                seconds INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bug_pointed_messages (
                message_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS idea_pointed_messages (
                message_id INTEGER PRIMARY KEY
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggest_pointed_messages (
                message_id INTEGER PRIMARY KEY
            )
        """)
        # Candies
        await db.execute("""
            CREATE TABLE IF NOT EXISTS candies (
                user_id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            )
        """)
        await db.commit()


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
    
    if member.bot:
        return
    
    now = datetime.datetime.utcnow()

    if before.channel and before.channel.id not in EXCLUDED_VC_IDS:
        key = (member.guild.id, member.id)
        join_time = voice_states.pop(key, None)
        if join_time:
            seconds = int((now - join_time).total_seconds())
            async with aiosqlite.connect("server_data.db") as db:
                async with db.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (member.id,)) as cursor:
                    row = await cursor.fetchone()
                if row:
                    total = row[0] + seconds
                    await db.execute("UPDATE voice_time SET seconds = ? WHERE user_id = ?", (total, member.id))
                else:
                    await db.execute("INSERT INTO voice_time (user_id, seconds) VALUES (?, ?)", (member.id, seconds))
                await db.commit()

    if after.channel and after.channel.id not in EXCLUDED_VC_IDS:
        voice_states[(member.guild.id, member.id)] = now

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
