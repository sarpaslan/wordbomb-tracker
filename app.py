from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask import make_response
import os
import sqlite3

app = Flask(__name__)
CORS(app)

# Rate limiting: 30 requests per minute per IP
limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

# Simple in-memory caching (you can later use Redis or other backends)
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})

@app.route("/")
def home():
    return jsonify({"message": "App is deployed and running!"})

@app.route("/api/user/<int:user_id>")
@limiter.limit("10 per minute")           # Individual limit for this route
@cache.memoize(timeout=60)                 # Cache results for 60 seconds
def api_user(user_id):
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "server_data.db")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {}

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

        return jsonify({"user_id": user_id, "stats": stats})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(jsonify({
        "error": "Rate limit exceeded",
        "message": str(e.description)
    }), 429)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
