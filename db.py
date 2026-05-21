import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "challenge.db")

CATEGORIES = [
    ("finance",  "💰 Финансы"),
    ("health",   "💪 Здоровье"),
    ("personal", "❤️ Личная жизнь"),
    ("growth",   "📚 Развитие"),
    ("rest",     "🌿 Отдых"),
]


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                name      TEXT NOT NULL,
                joined_at TEXT DEFAULT (date('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                day       INTEGER NOT NULL,
                category  TEXT    NOT NULL,
                goal_text TEXT    NOT NULL,
                done      INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, day, category)
            )
        """)
        conn.commit()


def register_user(user_id: int, name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        conn.commit()


def get_user(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT user_id, name FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row


def get_all_users():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT user_id, name FROM users").fetchall()


def save_goal(user_id: int, day: int, category: str, text: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO goals (user_id, day, category, goal_text, done)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(user_id, day, category) DO UPDATE SET goal_text = excluded.goal_text, done = 0
        """, (user_id, day, category, text))
        conn.commit()


def mark_done(user_id: int, day: int, category: str, done: bool):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE goals SET done = ? WHERE user_id = ? AND day = ? AND category = ?
        """, (int(done), user_id, day, category))
        conn.commit()


def get_goals(user_id: int, day: int) -> dict:
    """Returns {category: (goal_text, done)}"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT category, goal_text, done FROM goals WHERE user_id = ? AND day = ?",
            (user_id, day)
        ).fetchall()
    return {cat: (text, bool(done)) for cat, text, done in rows}


def get_user_stats(user_id: int) -> list:
    """Returns list of (day, total_goals, done_goals)"""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
            SELECT day,
                   COUNT(*) as total,
                   SUM(done) as done_count
            FROM goals
            WHERE user_id = ?
            GROUP BY day
            ORDER BY day
        """, (user_id,)).fetchall()


def get_weak_categories(user_id: int) -> list:
    """Returns categories sorted by completion rate ascending"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT category,
                   COUNT(*) as total,
                   SUM(done) as done_count,
                   ROUND(100.0 * SUM(done) / COUNT(*), 0) as pct
            FROM goals
            WHERE user_id = ?
            GROUP BY category
            ORDER BY pct ASC
        """, (user_id,)).fetchall()
    return rows
