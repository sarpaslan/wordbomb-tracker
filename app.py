from flask import Flask
import aiosqlite  # if you're using it in other code
import sqlite3    # use this for Flask web (simpler sync calls)
from discord.utils import get

app = Flask(__name__)

@app.route("/")
def home():
    return "hello world"

@app.route("/azaz")
def azaz():
    return "welcome azaz!"

@app.route("/user/<int:user_id>")
def show_user(user_id):
    try:
        # Open the DB connection
        conn = sqlite3.connect("/home/victorjiangvj/wordbomb-tracker/server_data.db")
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

