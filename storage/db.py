import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "body_double.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                whitelist TEXT DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                mode TEXT NOT NULL,
                started_at REAL NOT NULL,
                ended_at REAL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                app TEXT,
                title TEXT,
                url TEXT,
                session_id INTEGER
            );
        """)
        conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('global_whitelist', '[]')")
        conn.commit()


def get_projects():
    with _conn() as conn:
        rows = conn.execute("SELECT id, name, whitelist FROM projects").fetchall()
        return [{"id": r["id"], "name": r["name"], "whitelist": json.loads(r["whitelist"])} for r in rows]


def create_project(name: str):
    with _conn() as conn:
        cursor = conn.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        conn.commit()
        return {"id": cursor.lastrowid, "name": name, "whitelist": []}


def delete_project(project_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()


def update_project_whitelist(project_id: int, domains: list):
    with _conn() as conn:
        conn.execute("UPDATE projects SET whitelist = ? WHERE id = ?", (json.dumps(domains), project_id))
        conn.commit()


def get_global_whitelist():
    with _conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key = 'global_whitelist'").fetchone()
        return json.loads(row["value"]) if row else []


def update_global_whitelist(domains: list):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('global_whitelist', ?)",
            (json.dumps(domains),)
        )
        conn.commit()


def get_active_session():
    with _conn() as conn:
        row = conn.execute("""
            SELECT s.id, s.project_id, s.mode, s.started_at, p.name, p.whitelist
            FROM sessions s
            LEFT JOIN projects p ON s.project_id = p.id
            WHERE s.ended_at IS NULL
            ORDER BY s.started_at DESC LIMIT 1
        """).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "mode": row["mode"],
            "started_at": row["started_at"],
            "project_name": row["name"],
            "project_whitelist": json.loads(row["whitelist"]) if row["whitelist"] else [],
        }


def start_session(project_id: int, mode: str):
    end_session()
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (project_id, mode, started_at) VALUES (?, ?, ?)",
            (project_id, mode, time.time()),
        )
        conn.commit()
        return cursor.lastrowid


def end_session():
    with _conn() as conn:
        conn.execute("UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL", (time.time(),))
        conn.commit()


def save_event(event):
    session = get_active_session()
    session_id = session["id"] if session else None
    with _conn() as conn:
        conn.execute(
            "INSERT INTO events (timestamp, app, title, url, session_id) VALUES (?, ?, ?, ?, ?)",
            (event.timestamp, event.app, event.title, event.url, session_id),
        )
        conn.commit()
