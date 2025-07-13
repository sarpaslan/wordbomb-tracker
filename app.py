from flask import Flask, jsonify
from flask_cors import CORS
import os
import sqlite3

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"message": "🚀 App is deployed and running!"})

@app.route("/api/user/<int:user_id>")
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
