"""
db.py — minimal SQLite persistence for per-user conversation memory.
Kept intentionally simple: one table, four functions. Swap this out for
Postgres/Redis later if you ever need multi-instance deployment.
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
            role TEXT NOT NULL,       -- 'user' or 'model'
            content TEXT NOT NULL,
            created_at REAL NOT NULL
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
    """Return the last `limit` messages for this user, oldest first, in the
    {"role": ..., "parts": [...]} shape the Gemini SDK expects."""
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
    """Optional housekeeping: delete messages older than N days.
    Call this from a scheduled job if you want automatic data hygiene."""
    cutoff = time.time() - (days * 86400)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
    conn.commit()
    conn.close()