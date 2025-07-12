from flask import Flask
import aiosqlite  # if you're using it in other code
import sqlite3    # use this for Flask web (simpler sync calls)

app = Flask(__name__)

@app.route("/")
def home():
    return "hello world"

@app.route("/azaz")
def azaz():
    return "welcome azaz!"

import sqlite3

@app.route("/user/<int:user_id>")
def show_user(user_id):
    try:
        conn = sqlite3.connect("/home/victorjiangvj/wordbomb-tracker/server_data.db")
        cursor = conn.cursor()

        # Example: fetch voice time
        cursor.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if row:
            seconds = row[0]
            hours = round(seconds / 3600, 2)
            return f"User {user_id} has {seconds} seconds ({hours} hours) of voice time."
        else:
            return f"No data found for user {user_id}."

    except Exception as e:
        return f"Error: {str(e)}"
