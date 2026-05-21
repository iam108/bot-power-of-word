import os
import asyncio
import logging
from datetime import datetime, time
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

from db import init_db, mark_goal, get_day_status, get_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
TIMEZONE = pytz.timezone(os.environ.get("TZ", "Europe/Moscow"))

CATEGORIES = [
    ("💰", "Финансы",      "finance"),
    ("💪", "Здоровье",     "health"),
    ("❤️", "Личная жизнь", "personal"),
    ("📚", "Развитие",     "growth"),
    ("🌿", "Отдых",        "rest"),
]

START_DATE_STR = os.environ.get("START_DATE", "2025-01-01")
START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").date()


def get_day_number():
    today = datetime.now(TIMEZONE).date()
    delta = (today - START_DATE).days + 1
    return max(1, min(delta, 40))


def build_keyboard(session: str, day: int, statuses: dict):
    """Build inline keyboard. session = 'morning' or 'evening'"""
    rows = []
    for emoji, name, key in CATEGORIES:
        done = statuses.get(f"{session}_{key}", False)
        label = f"{'✅' if done else '☐'} {emoji} {name}"
        cb = f"{session}|{day}|{key}|{'off' if done else 'on'}"
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(rows)


async def send_morning(context: ContextTypes.DEFAULT_TYPE):
    day = get_day_number()
    if day > 40:
        return
    statuses = get_day_status(day)
    kb = build_keyboard("morning", day, statuses)
    text = (
        f"🌅 *День {day}/40 — цели на сегодня*\n\n"
        f"Отметьте каждое направление после того,\n"
        f"как поставили цель в посте ↓"
    )
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def send_evening(context: ContextTypes.DEFAULT_TYPE):
    day = get_day_number()
    if day > 40:
        return
    statuses = get_day_status(day)
    kb = build_keyboard("evening", day, statuses)
    text = (
        f"🌙 *День {day}/40 — итог дня*\n\n"
        f"Отметьте каждое направление после того,\n"
        f"как написали вечерний отчёт ↓"
    )
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=kb,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    if len(parts) != 4:
        return

    session, day_str, key, action = parts
    day = int(day_str)
    checked = (action == "on")

    mark_goal(day, session, key, checked)

    statuses = get_day_status(day)
    kb = build_keyboard(session, day, statuses)

    await query.edit_message_reply_markup(reply_markup=kb)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_stats()
    if not rows:
        await update.message.reply_text("Пока нет данных.")
        return

    lines = ["📊 *Статистика вызова*\n"]
    for day, m_count, e_count in rows:
        m_bar = "🟣" * m_count + "⬜" * (5 - m_count)
        e_bar = "🟢" * e_count + "⬜" * (5 - e_count)
        lines.append(f"День {day:>2}  🌅{m_bar}  🌙{e_bar}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я трекер 40-дневного вызова.\n\n"
        "Каждое утро в 09:45 пришлю кнопки для утренних целей,\n"
        "каждый вечер в 21:45 — для вечерних отчётов.\n\n"
        "Команды:\n"
        "/stats — статистика по всем дням\n"
        "/today — кнопки на сегодня вручную"
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = get_day_number()
    statuses = get_day_status(day)

    for session, label in [("morning", "🌅 Утро"), ("evening", "🌙 Вечер")]:
        kb = build_keyboard(session, day, statuses)
        await update.message.reply_text(
            f"{label} — день {day}/40",
            reply_markup=kb,
        )


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CallbackQueryHandler(button_handler))

    jq = app.job_queue
    tz = TIMEZONE
    jq.run_daily(send_morning, time=time(9, 45, tzinfo=tz))
    jq.run_daily(send_evening, time=time(21, 45, tzinfo=tz))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
