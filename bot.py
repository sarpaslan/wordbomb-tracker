import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import aiosqlite

# Load token
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Logging setup
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, log_handler=handler, log_level=logging.DEBUG, help_command=None)

# Threshold-based roles
MESSAGE_THRESHOLDS = {
    100: "Active",
    2000: "Veteran",
    10000: "Elite"
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
}

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
    "Word Bomb Tracker": ["!leaderboard - Get information on the leaderboard",
                          "!help - Get help on the usage of commands"]
}

@bot.event
async def on_ready():
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
        await db.commit()

@bot.event
async def on_message(message):
    #print(f"[DEBUG] Message from {message.author}: {message.content}")
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.channel.id in EXCLUDED_CHANNEL_IDS:
        return

    # Message tracking
    async with aiosqlite.connect("server_data.db") as db:
        user_id = message.author.id
        async with db.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            new_count = row[0] + 1
            await db.execute("UPDATE messages SET count = ? WHERE user_id = ?", (new_count, user_id))
        else:
            new_count = 1
            await db.execute("INSERT INTO messages (user_id, count) VALUES (?, ?)", (user_id, 1))

        await db.commit()
        #print(f"[DEBUG] {message.author} now has {new_count} messages.")

    # Assign roles if needed
    await assign_roles(message.author, new_count, message.guild)

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
    HECTOR_ID = 265196052192165888 #switch to hector's id
    SUGGEST_REACTION = "☑️"
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
        print(f"[DEBUG] {author} now has {new_count} points in suggest_points.")
        return

    # Bug / Idea system
    if payload.user_id != HECTOR_ID:
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
    await channel.send(f"✅ {role_name} point recorded for {author.mention}!")

    # If it's a BUG, log to file
    if payload.emoji.name == BUG_EMOJI:
        with open("bugs.log", "a", encoding="utf-8") as logfile:
            logfile.write(
                f"[BUG] {author} ({author.id}) in #{channel.name}:\n"
                f"Message: {message.content}\n"
                f"Link: {message.jump_url}\n"
                f"{'-' * 60}\n"
            )
        print("[DEBUG] Bug logged to file.")

    # 💡 If it's an IDEA, forward to mod-ideas channel
    elif payload.emoji.name == IDEA_EMOJI:
        mod_ideas_channel = guild.get_channel(1384753231820886108)  # mod ideas channel id
        if mod_ideas_channel:
            await mod_ideas_channel.send(
                f"☑️ **Approved Idea** by {author.mention}:\n{message.content}\n🔗 {message.jump_url}"
            )
        print("[DEBUG] Idea forwarded to mod-ideas channel.")

    if new_count >= POINT_THRESHOLD:
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(author.id)
        if role and role not in member.roles:
            await member.add_roles(role)
            print(f"[DEBUG] {author.name} was given the '{role_name}' role.")

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

    @discord.ui.button(label="Suggestions", style=discord.ButtonStyle.primary, custom_id="category_suggestions")
    async def suggestions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "suggestions", 1, self.author_id)

    @discord.ui.button(label="Messages", style=discord.ButtonStyle.primary, custom_id="category_messages")
    async def messages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "messages", 1, self.author_id)

    @discord.ui.button(label="Bugs", style=discord.ButtonStyle.primary, custom_id="category_bugs")
    async def bugs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "bugs", 1, self.author_id)

    @discord.ui.button(label="Ideas", style=discord.ButtonStyle.primary, custom_id="category_ideas")
    async def ideas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard(interaction, "ideas", 1, self.author_id)

@bot.command()
async def leaderboard(ctx, category: str = "suggestions"):
    await update_leaderboard(ctx, category.lower(), 1, ctx.author.id)

async def update_leaderboard(ctx_or_interaction, category, page, author_id):
    table_map = {
        "suggestions": "suggest_points",
        "messages": "messages",
        "bugs": "bug_points",
        "ideas": "idea_points"
    }

    label_map = {
        "suggestions": "suggestions",
        "messages": "messages",
        "bugs": "bugs found",
        "ideas": "ideas"
    }

    if category not in table_map:
        await ctx_or_interaction.response.send_message(
            "Invalid category. Use: suggestions, messages, bugs, ideas.",
            ephemeral=True
        )
        return

    table = table_map[category]
    unit = label_map[category]

    async with aiosqlite.connect("server_data.db") as db:
        async with db.execute(f"SELECT user_id, count FROM {table} ORDER BY count DESC") as cursor:
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

        line = f"{i}. {username} • **{count} {unit}**"
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

            line = f"10. {username} • **{count} {unit}**"
            if user_id == author_id:
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


@bot.command(name="help")
async def show_help(ctx):

    embed = discord.Embed(
        title="📚 Server Commands Overview",
        description="Here are the commands from our bots in this server:?",
        color=discord.Color.blue()
    )

    for bot_name, cmds in OTHER_BOTS_COMMANDS.items():
        if cmds:
            command_list = "\n".join(cmds)
            embed.add_field(name=bot_name, value=command_list, inline=False)

    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"Error in command {ctx.command}: {error}")

bot.run(token)
