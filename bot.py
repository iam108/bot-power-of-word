import os
import logging
from datetime import datetime, time, date
import pytz

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes,
    filters
)

from db import (
    init_db, register_user, get_user, get_all_users,
    save_goal, mark_done, get_goals, get_user_stats,
    get_weak_categories, CATEGORIES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN     = os.environ["BOT_TOKEN"]
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])
TIMEZONE      = pytz.timezone(os.environ.get("TZ", "Europe/Moscow"))
START_DATE    = datetime.strptime(
    os.environ.get("START_DATE", "2025-01-01"), "%Y-%m-%d"
).date()

ASK_NAME = 0

BTN_GOALS  = "🌅 Цели на день"
BTN_REPORT = "🌙 Вечерний отчёт"
BTN_STATS  = "📊 Моя статистика"
BTN_WEAK   = "⚠️ Где проседаю"


def main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_GOALS), KeyboardButton(BTN_REPORT)],
         [KeyboardButton(BTN_STATS), KeyboardButton(BTN_WEAK)]],
        resize_keyboard=True,
        persistent=True
    )


def get_day_number() -> int:
    today = datetime.now(TIMEZONE).date()
    delta = (today - START_DATE).days + 1
    return max(1, min(delta, 40))


def cat_label(key: str) -> str:
    return dict(CATEGORIES)[key]


# ─── Setup bot commands ───────────────────────────────────────────────────────

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",  "🚀 Старт / главное меню"),
        BotCommand("goals",  "🌅 Поставить цели на день"),
        BotCommand("report", "🌙 Вечерний отчёт"),
        BotCommand("stats",  "📊 Моя статистика"),
        BotCommand("weak",   "⚠️ Где проседаю"),
    ])


# ─── Registration ─────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"👋 Привет, *{user[1]}*!\n\nВыбери действие в меню ниже 👇",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Привет! Это трекер *40-дневного вызова*.\n\n"
        "Каждое утро ты ставишь 5 целей — по одной на каждую сферу жизни.\n"
        "Вечером отмечаешь что выполнено. Всё автоматически уходит в группу.\n\n"
        "Как тебя зовут? Имя будет видно в постах группы.",
        parse_mode="Markdown"
    )
    return ASK_NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 50:
        await update.message.reply_text("Введи имя (не длиннее 50 символов):")
        return ASK_NAME

    register_user(update.effective_user.id, name)
    await update.message.reply_text(
        f"✅ Отлично, *{name}*! Ты в игре 🚀\n\n"
        f"Напоминания:\n"
        f"  🌅 08:00 — поставить цели\n"
        f"  🌙 20:00 — вечерний отчёт\n\n"
        f"Или используй кнопки ниже в любой момент 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


# ─── Goals collection ─────────────────────────────────────────────────────────

async def start_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return ConversationHandler.END

    day = get_day_number()
    context.user_data["day"] = day
    context.user_data["goals_collected"] = {}

    key, label = CATEGORIES[0]
    await update.message.reply_text(
        f"📋 *День {day}/40 — цели на сегодня*\n\n"
        f"Буду спрашивать по одной сфере.\n\n"
        f"1️⃣  {label}\n\nНапиши цель:",
        parse_mode="Markdown"
    )
    return 1


async def collect_step(update: Update, context: ContextTypes.DEFAULT_TYPE, step: int):
    text = update.message.text.strip()
    key, label = CATEGORIES[step - 1]

    if not text:
        await update.message.reply_text(f"Напиши цель для {label}:")
        return step

    context.user_data["goals_collected"][key] = text

    if step < 5:
        nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
        nkey, nlabel = CATEGORIES[step]
        await update.message.reply_text(
            f"{nums[step]}  {nlabel}\n\nНапиши цель:",
            parse_mode="Markdown"
        )
        return step + 1
    else:
        return await finish_goals(update, context)


async def finish_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    day = context.user_data["day"]
    goals = context.user_data["goals_collected"]

    for key, text in goals.items():
        save_goal(user_id, day, key, text)

    post = build_morning_post(user[1], day, goals)
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post, parse_mode="Markdown")

    await update.message.reply_text(
        "✅ *Цели сохранены и отправлены в группу!*\n\n"
        "Вечером нажми *🌙 Вечерний отчёт* чтобы отметить выполненное.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


def build_morning_post(name: str, day: int, goals: dict) -> str:
    lines = [f"🌅 *{name} — День {day}/40*\n"]
    for key, label in CATEGORIES:
        lines.append(f"{label}\n▸ {goals.get(key, '—')}\n")
    lines.append(f"#день{day} #утро")
    return "\n".join(lines)


async def g1(u,c): return await collect_step(u,c,1)
async def g2(u,c): return await collect_step(u,c,2)
async def g3(u,c): return await collect_step(u,c,3)
async def g4(u,c): return await collect_step(u,c,4)
async def g5(u,c): return await collect_step(u,c,5)


# ─── Evening report ───────────────────────────────────────────────────────────

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return

    day = get_day_number()
    goals = get_goals(user_id, day)
    if not goals:
        await update.message.reply_text(
            "Сначала поставь цели на сегодня 👉 *🌅 Цели на день*",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

    kb = build_report_keyboard(user_id, day, goals)
    await update.message.reply_text(
        f"🌙 *День {day}/40 — что выполнено?*\n\nНажимай на каждую сферу:",
        parse_mode="Markdown",
        reply_markup=kb
    )


def build_report_keyboard(user_id, day, goals):
    rows = []
    for key, label in CATEGORIES:
        if key not in goals:
            continue
        goal_text, done = goals[key]
        tick = "✅" if done else "☐"
        short = goal_text[:25] + "…" if len(goal_text) > 25 else goal_text
        rows.append([InlineKeyboardButton(
            f"{tick} {label}: {short}",
            callback_data=f"rep|{user_id}|{day}|{key}|{'off' if done else 'on'}"
        )])
    rows.append([InlineKeyboardButton(
        "📤 Отправить отчёт в группу",
        callback_data=f"rep_send|{user_id}|{day}"
    )])
    return InlineKeyboardMarkup(rows)


async def report_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|")

    if parts[0] == "rep_send":
        user_id, day = int(parts[1]), int(parts[2])
        user = get_user(user_id)
        goals = get_goals(user_id, day)
        post = build_evening_post(user[1], day, goals)
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=post, parse_mode="Markdown")
        await query.edit_message_text("✅ Отчёт отправлен в группу!")
        weak = get_weak_categories(user_id)
        if weak:
            await send_weak_msg(context, user_id, weak)
        return

    _, uid, day_str, key, action = parts
    if query.from_user.id != int(uid):
        await query.answer("Это не твой отчёт 😉", show_alert=True)
        return

    mark_done(int(uid), int(day_str), key, action == "on")
    goals = get_goals(int(uid), int(day_str))
    await query.edit_message_reply_markup(
        reply_markup=build_report_keyboard(int(uid), int(day_str), goals)
    )


def build_evening_post(name, day, goals):
    lines = [f"🌙 *{name} — День {day}/40 — итог*\n"]
    done_count = 0
    for key, label in CATEGORIES:
        if key not in goals:
            continue
        text, done = goals[key]
        lines.append(f"{'✅' if done else '❌'} {label}\n▸ {text}\n")
        if done: done_count += 1
    lines.append(f"Выполнено: *{done_count}/5*\n#день{day} #вечер")
    return "\n".join(lines)


async def send_weak_msg(context, user_id, weak):
    lines = ["📊 *Анализ по сферам:*\n"]
    for cat, total, done_c, pct in weak:
        label = cat_label(cat)
        p = int(pct or 0)
        bar = "█" * (p // 10) + "░" * (10 - p // 10)
        lines.append(f"{label}\n{bar} {p}%\n")
    await context.bot.send_message(chat_id=user_id, text="\n".join(lines), parse_mode="Markdown")


# ─── Stats & Weak ─────────────────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return
    rows = get_user_stats(user_id)
    if not rows:
        await update.message.reply_text("Пока нет данных.", reply_markup=main_keyboard())
        return
    lines = [f"📊 *Статистика — {user[1]}*\n"]
    for day, total, done_c in rows:
        filled = done_c or 0
        lines.append(f"День {day:>2}  {'🟣'*filled}{'⬜'*(5-filled)}  {filled}/5")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard())


async def cmd_weak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return
    weak = get_weak_categories(user_id)
    if not weak:
        await update.message.reply_text("Пока нет данных.", reply_markup=main_keyboard())
        return
    await send_weak_msg(context, user_id, weak)


# ─── Button text handlers ─────────────────────────────────────────────────────

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == BTN_STATS:
        await cmd_stats(update, context)
    elif text == BTN_WEAK:
        await cmd_weak(update, context)
    elif text == BTN_REPORT:
        await start_report(update, context)


# ─── Scheduled reminders ──────────────────────────────────────────────────────

async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    day = get_day_number()
    if day > 40: return
    for user_id, name in get_all_users():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"☀️ Доброе утро, *{name}*!\n\n"
                    f"День *{day}/40* — время поставить цели 💪\n\n"
                    f"Нажми 👉 *🌅 Цели на день*"
                ),
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
        except Exception as e:
            logger.warning(f"Morning reminder failed for {user_id}: {e}")


async def job_evening(context: ContextTypes.DEFAULT_TYPE):
    day = get_day_number()
    if day > 40: return
    for user_id, name in get_all_users():
        try:
            goals = get_goals(user_id, day)
            if not goals: continue
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🌙 Добрый вечер, *{name}*!\n\n"
                    f"День *{day}/40* — как прошёл день?\n\n"
                    f"Нажми 👉 *🌙 Вечерний отчёт*"
                ),
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
        except Exception as e:
            logger.warning(f"Evening reminder failed for {user_id}: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    reg = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)]},
        fallbacks=[],
    )

    goals_conv = ConversationHandler(
        entry_points=[
            CommandHandler("goals", start_goals),
            MessageHandler(filters.Regex(f"^{BTN_GOALS}$"), start_goals),
        ],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, g1)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, g2)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, g3)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, g4)],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, g5)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
    )

    app.add_handler(reg)
    app.add_handler(goals_conv)
    app.add_handler(CommandHandler("report", start_report))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("weak", cmd_weak))
    app.add_handler(CallbackQueryHandler(report_button, pattern=r"^rep"))
    app.add_handler(MessageHandler(
        filters.Regex(f"^({BTN_REPORT}|{BTN_STATS}|{BTN_WEAK})$"),
        handle_buttons
    ))

    tz = TIMEZONE
    app.job_queue.run_daily(job_morning, time=time(8, 0, tzinfo=tz))
    app.job_queue.run_daily(job_evening, time=time(20, 0, tzinfo=tz))

    logger.info("Bot v3 started")
    app.run_polling()


if __name__ == "__main__":
    main()
