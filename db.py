import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "./jobsearch.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access
    return conn

def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                structured_profile TEXT,       -- JSON
                full_resume_text TEXT,
                user_answers TEXT,             -- JSON
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
    print("Database initialized.")

def upsert_user(user_id: str, structured_profile: dict, full_resume_text: str, user_answers: dict):
    """Insert or update a user record."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO users (user_id, structured_profile, full_resume_text, user_answers, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                structured_profile = excluded.structured_profile,
                full_resume_text    = excluded.full_resume_text,
                user_answers        = excluded.user_answers,
                updated_at          = excluded.updated_at
        """, (
            user_id,
            json.dumps(structured_profile),
            full_resume_text,
            json.dumps(user_answers),
            now,
            now
        ))
        conn.commit()
    print(f"User {user_id} saved to DB.")

def get_user(user_id: str) -> dict | None:
    """Fetch a user record by user_id."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "structured_profile": json.loads(row["structured_profile"]),
        "full_resume_text": row["full_resume_text"],
        "user_answers": json.loads(row["user_answers"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }