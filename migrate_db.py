import sqlite3
import os

def migrate_database():
    """
    This script renames the 'date' column to 'week' in the message_history table.
    It should only be run ONCE.
    """
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(BASE_DIR, "server_data.db")

        if not os.path.exists(DB_PATH):
            print(f"Error: Database file not found at {DB_PATH}")
            return

        print(f"Connecting to database at {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Attempting to rename 'date' column to 'week' in 'message_history' table...")
        
        # This is the command that renames the column
        cursor.execute("ALTER TABLE message_history RENAME COLUMN date TO week")
        
        conn.commit()
        print("✅ Successfully renamed column.")

    except sqlite3.OperationalError as e:
        # This will likely happen if you run the script more than once.
        if "duplicate column name: week" in str(e) or "no such column: date" in str(e):
            print("⚠️  Warning: Column might have already been renamed. The error suggests the operation is complete.")
        else:
            print(f"❌ An unexpected database error occurred: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    migrate_database()