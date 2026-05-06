import sqlite3
import json
from pathlib import Path

DB_PATH = Path("storage") / "body_double.db"

def view_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        print("=== PROJECTS ===")
        projects = conn.execute("SELECT * FROM projects").fetchall()
        for p in projects:
            print(f"ID: {p['id']}, Name: {p['name']}, Whitelist: {json.loads(p['whitelist'])}")

        print("\n=== CONFIG ===")
        config = conn.execute("SELECT * FROM config").fetchall()
        for c in config:
            print(f"Key: {c['key']}, Value: {json.loads(c['value'])}")

        print("\n=== SESSIONS ===")
        sessions = conn.execute("SELECT * FROM sessions").fetchall()
        for s in sessions:
            print(f"ID: {s['id']}, Project ID: {s['project_id']}, Mode: {s['mode']}, Started: {s['started_at']}, Ended: {s['ended_at']}")

        print("\n=== EVENTS (last 10) ===")
        events = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 10").fetchall()
        for e in events:
            print(f"ID: {e['id']}, Timestamp: {e['timestamp']}, App: {e['app']}, Title: {e['title']}, URL: {e['url']}, Session ID: {e['session_id']}")

def clear_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM config")
        conn.commit()
    print("Database cleared!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_database()
    else:
        view_database()