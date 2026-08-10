"""
db.py — SQLite persistence for per-user conversation memory + proactive
message tracking.
"""

import sqlite3
import time

from config import DB_PATH, MAX_HISTORY_MESSAGES


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proactive_state (
            user_id INTEGER PRIMARY KEY,
            last_proactive_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_message(user_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = MAX_HISTORY_MESSAGES):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    rows.reverse()
    return [{"role": r, "parts": [c]} for r, c in rows]


def clear_history(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def purge_older_than(days: int):
    cutoff = time.time() - (days * 86400)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def get_all_user_ids():
    """All user_ids who have ever sent a message — used by the proactive
    job when OWNER_USER_ID isn't set."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT user_id FROM messages").fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_last_message_time(user_id: int):
    """Timestamp of this user's most recent message (either direction), or
    None if they've never messaged."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT MAX(created_at) FROM messages WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


def get_last_proactive_time(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT last_proactive_at FROM proactive_state WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_last_proactive_time(user_id: int, ts: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO proactive_state (user_id, last_proactive_at) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_proactive_at = excluded.last_proactive_at
        """,
        (user_id, ts),
    )
    conn.commit()
    conn.close()