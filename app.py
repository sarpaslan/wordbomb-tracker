from flask import Flask, jsonify, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import os
import sqlite3
import requests

app = Flask(__name__)
CORS(app)

# --- Configuration ---
# It's recommended to use environment variables for sensitive data like the bot token.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Rate limiting: 30 requests per minute per IP
limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

# Simple in-memory caching
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})

def get_discord_user(user_id):
    """Fetches a Discord user's profile using the Discord API."""
    if not DISCORD_BOT_TOKEN:
        return None
    
    url = f"https://discord.com/api/v9/users/{user_id}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Discord user: {e}")
        return None

@app.route("/")
def home():
    return jsonify({"message": "App is deployed and running!"})

@app.route("/api/user/<int:user_id>")
@limiter.limit("10 per minute")
@cache.memoize(timeout=60)
def api_user(user_id):
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "server_data.db")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {}

        # Your database queries remain the same
        cursor.execute("SELECT seconds FROM voice_time WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            seconds = row[0]
            stats["voice_time_seconds"] = seconds
            stats["voice_time_hours"] = round(seconds / 3600, 2)

        cursor.execute("SELECT count FROM messages WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["messages"] = row[0]

        cursor.execute("SELECT count FROM bug_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["bug_points"] = row[0]

        cursor.execute("SELECT count FROM idea_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["idea_points"] = row[0]

        cursor.execute("SELECT count FROM suggest_points WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["suggest_points"] = row[0]

        cursor.execute("SELECT count FROM candies WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            stats["candies"] = row[0]

        conn.close()

        if not stats:
            return jsonify({"error": f"No data found for user {user_id}."}), 404
        
        # Fetch Discord user information
        discord_user = get_discord_user(user_id)
        username = discord_user.get('username') if discord_user else "Unknown"

        response_data = {
            "user_id": user_id,
            "discord_username": username,
            "stats": stats
        }

        response = make_response(jsonify(response_data))
        response.headers["Cache-Control"] = "public, max-age=120, immutable"
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(jsonify({
        "error": "Rate limit exceeded",
        "message": str(e.description)
    }), 429)

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("Warning: DISCORD_BOT_TOKEN environment variable is not set.")
    app.run(host="0.0.0.0", port=5000)