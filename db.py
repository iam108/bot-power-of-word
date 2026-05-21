import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "challenge.db")

CATEGORIES = ["finance", "health", "personal", "growth", "rest"]
SESSIONS   = ["morning", "evening"]


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                day      INTEGER NOT NULL,
                session  TEXT    NOT NULL,
                category TEXT    NOT NULL,
                done     INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, session, category)
            )
        """)
        conn.commit()


def mark_goal(day: int, session: str, category: str, done: bool):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO goals (day, session, category, done)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day, session, category) DO UPDATE SET done = excluded.done
        """, (day, session, category, int(done)))
        conn.commit()


def get_day_status(day: int) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT session, category, done FROM goals WHERE day = ?", (day,)
        ).fetchall()
    return {f"{session}_{category}": bool(done) for session, category, done in rows}


def get_stats():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT day,
                   SUM(CASE WHEN session='morning' AND done=1 THEN 1 ELSE 0 END) as m,
                   SUM(CASE WHEN session='evening' AND done=1 THEN 1 ELSE 0 END) as e
            FROM goals
            GROUP BY day
            ORDER BY day
        """).fetchall()
    return rows
