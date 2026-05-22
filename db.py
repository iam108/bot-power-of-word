import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

CATEGORIES = [
    ("finance",  "💰 Финансы"),
    ("health",   "💪 Здоровье"),
    ("personal", "❤️ Личная жизнь"),
    ("growth",   "📚 Развитие"),
    ("rest",     "🌿 Отдых"),
]


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id   BIGINT PRIMARY KEY,
                    name      TEXT NOT NULL,
                    joined_at DATE DEFAULT CURRENT_DATE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id        SERIAL PRIMARY KEY,
                    user_id   BIGINT NOT NULL,
                    day       INTEGER NOT NULL,
                    category  TEXT NOT NULL,
                    goal_text TEXT NOT NULL,
                    done      BOOLEAN NOT NULL DEFAULT FALSE,
                    UNIQUE(user_id, day, category)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pushups (
                    user_id BIGINT NOT NULL,
                    day     INTEGER NOT NULL,
                    done    BOOLEAN NOT NULL DEFAULT FALSE,
                    PRIMARY KEY (user_id, day)
                )
            """)
        conn.commit()


def register_user(user_id: int, name: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, name)
            )
        conn.commit()


def get_user(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, name FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone()


def get_all_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, name FROM users")
            return cur.fetchall()


def save_goal(user_id: int, day: int, category: str, text: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO goals (user_id, day, category, goal_text, done)
                VALUES (%s, %s, %s, %s, FALSE)
                ON CONFLICT (user_id, day, category)
                DO UPDATE SET goal_text = EXCLUDED.goal_text, done = FALSE
            """, (user_id, day, category, text))
        conn.commit()


def mark_done(user_id: int, day: int, category: str, done: bool):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE goals SET done = %s WHERE user_id = %s AND day = %s AND category = %s",
                (done, user_id, day, category)
            )
        conn.commit()


def get_goals(user_id: int, day: int) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category, goal_text, done FROM goals WHERE user_id = %s AND day = %s",
                (user_id, day)
            )
            rows = cur.fetchall()
    return {cat: (text, bool(done)) for cat, text, done in rows}


def mark_pushups(user_id: int, day: int, done: bool):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pushups (user_id, day, done) VALUES (%s, %s, %s)
                ON CONFLICT (user_id, day) DO UPDATE SET done = EXCLUDED.done
            """, (user_id, day, done))
        conn.commit()


def get_pushups(user_id: int, day: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT done FROM pushups WHERE user_id = %s AND day = %s", (user_id, day))
            row = cur.fetchone()
    return bool(row[0]) if row else False


def get_user_stats(user_id: int) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT day, COUNT(*) as total,
                       SUM(CASE WHEN done THEN 1 ELSE 0 END) as done_count
                FROM goals WHERE user_id = %s
                GROUP BY day ORDER BY day
            """, (user_id,))
            return cur.fetchall()


def get_weak_categories(user_id: int) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category, COUNT(*) as total,
                       SUM(CASE WHEN done THEN 1 ELSE 0 END) as done_count,
                       ROUND(100.0 * SUM(CASE WHEN done THEN 1 ELSE 0 END) / COUNT(*), 0) as pct
                FROM goals WHERE user_id = %s
                GROUP BY category ORDER BY pct ASC
            """, (user_id,))
            return cur.fetchall()


def cat_label(key: str) -> str:
    return dict(CATEGORIES)[key]
