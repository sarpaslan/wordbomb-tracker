from flask import Flask
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import sqlite3

app = Flask(__name__)

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

@app.route("/user/<int:user_id>")
def show_user(user_id):
    try:
        # Open the DB connection

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "server_data.db")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {}

        # Voice time
        cursor.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            seconds = row[0]
            stats["Voice Time"] = f"{seconds} seconds ({round(seconds / 3600, 2)} hours)"

        # Messages
        cursor.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["Messages"] = row[0]

        # Bug points
        cursor.execute("SELECT count FROM bug_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["Bug Points"] = row[0]

        # Idea points
        cursor.execute("SELECT count FROM idea_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["Idea Points"] = row[0]

        # Suggest points
        cursor.execute("SELECT count FROM suggest_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["Suggest Points"] = row[0]

        # Candies
        cursor.execute("SELECT count FROM candies WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["Candies"] = row[0]

        # Attempt to get user's display name from Discord cache
        display_name = str(user_id)  # default
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                display_name = member.display_name
                break

        if not stats:
            return f"No data found for user {display_name}."

        # Build the response
        response = f"Stats for {display_name}:\n"
        for key, value in stats.items():
            response += f"- {key}: {value}\n"

        return response

    except Exception as e:
        return f"Error: {str(e)}"
    

if __name__ == "__main__":
    app.run()