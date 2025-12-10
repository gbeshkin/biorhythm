import os
import math
from datetime import datetime, date

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

ASK_DOB = 1


def parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def calc_biorhythm(birth_date: date, target_date: date | None = None) -> dict[str, float]:
    if target_date is None:
        target_date = date.today()

    days = (target_date - birth_date).days
    if days < 0:
        raise ValueError("Target date is before birth date")

    cycles = {
        "physical": 23,
        "emotional": 28,
        "intellectual": 33,
    }

    result = {}
    for name, period in cycles.items():
        value = math.sin(2 * math.pi * days / period) * 100
        result[name] = round(value, 2)
    return result


def format_bio_text(target_date: date, bio: dict[str, float]) -> str:
    def sign(v: float) -> str:
        return f"+{v}" if v > 0 else f"{v}"

    return (
        f"Биоритмы на {target_date.strftime('%d.%m.%Y')}\n"
        f"Физический: {sign(bio['physical'])}%\n"
        f"Эмоциональный: {sign(bio['emotional'])}%\n"
        f"Интеллектуальный: {sign(bio['intellectual'])}%"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_text(
        "Привет, {name}! Я бот календаря биоритмов.\n"
        "⚠️ Важно: биоритмы — псевдонаучная теория, пользуемся ими ради интереса, "
        "а не как медицинским советом.\n\n"
        "Для начала пришли свою дату рождения в формате ДД.ММ.ГГГГ "
        "(например, 05.03.1990)."
        .format(name=user.first_name or "друг")
    )
    return ASK_DOB


async def set_dob(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    dob = parse_date(text)
    if not dob:
        await update.message.reply_text(
            "Не получилось распознать дату 😕\n"
            "Попробуй ещё раз в формате ДД.ММ.ГГГГ, например 05.03.1990."
        )
        return ASK_DOB

    context.user_data["dob"] = dob.isoformat()

    bio_today = calc_biorhythm(dob)
    msg = (
        "Отлично! Я запомнил твою дату рождения: {dob}\n\n"
        "{bio}\n\n"
        "Команды, которые я понимаю:\n"
        "/today — биоритмы на сегодня\n"
        "/on YYYY-MM-DD — биоритмы на конкретную дату (например, /on 2025-12-31)\n"
        "/help — подсказка по возможностям бота"
    ).format(
        dob=dob.strftime('%d.%m.%Y'),
        bio=format_bio_text(date.today(), bio_today),
    )
    await update.message.reply_text(msg)
    return ConversationHandler.END


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dob_iso = context.user_data.get("dob")
    if not dob_iso:
        await update.message.reply_text(
            "Я ещё не знаю твою дату рождения. Отправь /start и введи её."
        )
        return

    dob = date.fromisoformat(dob_iso)
    bio = calc_biorhythm(dob)
    await update.message.reply_text(format_bio_text(date.today(), bio))


async def on_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dob_iso = context.user_data.get("dob")
    if not dob_iso:
        await update.message.reply_text(
            "Я ещё не знаю твою дату рождения. Отправь /start и введи её."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /on YYYY-MM-DD, например /on 2025-12-31."
        )
        return

    try:
        target = datetime.strptime(context.args[0], "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text(
            "Не получилось распознать дату. Используй формат YYYY-MM-DD, "
            "например 2025-12-31."
        )
        return

    dob = date.fromisoformat(dob_iso)
    try:
        bio = calc_biorhythm(dob, target)
    except ValueError:
        await update.message.reply_text(
            "Дата для расчёта не может быть раньше даты рождения."
        )
        return

    await update.message.reply_text(format_bio_text(target, bio))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Я показываю твой календарь биоритмов. Основные команды:\n"
        "/start — заново ввести дату рождения\n"
        "/today — биоритмы на сегодня\n"
        "/on YYYY-MM-DD — биоритмы на выбранную дату\n"
        "\nПомни, что биоритмы — развлечение, а не наука 😉"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Окей, отменяем ввод даты рождения. Можешь начать заново командой /start."
    )
    return ConversationHandler.END


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Please set BOT_TOKEN environment variable")

    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_DOB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_dob),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("on", on_date))
    application.add_handler(CommandHandler("help", help_cmd))

    application.run_polling()


if __name__ == "__main__":
    main()
