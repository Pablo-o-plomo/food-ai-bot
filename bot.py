import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food
from voice_ai import transcribe_voice
from users_db import add_food, get_day, undo_last, reset_day
from coach_ai import coach_reply

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")


def extract_nutrition(text):
    try:
        calories = re.search(r"Калории:\s*([\d\.]+)", text)
        protein = re.search(r"Белки:\s*([\d\.]+)", text)
        fat = re.search(r"Жиры:\s*([\d\.]+)", text)
        carbs = re.search(r"Углеводы:\s*([\d\.]+)", text)
        return (
            float(calories.group(1)),
            float(protein.group(1)),
            float(fat.group(1)),
            float(carbs.group(1))
        )
    except:
        return None


def is_undo_text(t: str) -> bool:
    t = (t or "").lower()
    keys = ["убери", "удали", "отмени", "ошибка", "не то", "не так", "верни назад", "undo"]
    return any(k in t for k in keys)


# -------- Команды --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋 Я — AI нутрициолог и дневник питания 🍽\n\n"
        "Как пользоваться:\n"
        "📸 фото еды / ✍️ текст / 🎤 голос\n\n"
        "Команды:\n"
        "📊 /today — отчёт за день\n"
        "↩️ /undo — отменить последний приём пищи\n"
        "🧹 /reset — очистить день\n"
        "🍱 /plan — план питания (скоро станет персональным)\n"
        "✨ /want — скажи, чего хочется (подберу варианты)\n"
    )


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    day = get_day(user_id)
    await update.message.reply_text(
        "📊 Сегодня у тебя:\n"
        f"Калории: {round(day['calories'])} ккал\n"
        f"Белки: {round(day['protein'])} г\n"
        f"Жиры: {round(day['fat'])} г\n"
        f"Углеводы: {round(day['carbs'])} г"
    )


async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    day = undo_last(user_id)
    if not day:
        await update.message.reply_text("Пока нечего отменять ↩️🙂")
        return
    await update.message.reply_text(
        "Откатил последний приём пищи ↩️\n\n"
        "📊 Сейчас за сегодня:\n"
        f"{round(day['calories'])} ккал\n"
        f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    reset_day(user_id)
    await update.message.reply_text("Готово 🧹 Обнулил день. Начинаем заново 🙂")


async def want_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Окей 😋 Чего хочется?\n\n"
        "Напиши одним словом или фразой:\n"
        "🍫 сладкое / 🧂 солёное / 🍗 мясо / 🥗 лёгкое / 🍝 сытное / ☕️ кофе\n\n"
        "И я подкину варианты 👇"
    )


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍱 План на день (база):\n"
        "Завтрак: белок + сложные угли (омлет/овсянка)\n"
        "Обед: белок + гарнир + овощи (курица/рыба + рис/гречка)\n"
        "Перекус: фрукт/йогурт/орехи\n"
        "Ужин: белок + овощи (творог/рыба/салат)\n\n"
        "Хочешь план под цель — сделаем /goal и /profile 😉"
    )


# -------- Универсальная запись в дневник --------
async def handle_nutrition(update: Update, nutrition_text: str):
    nutrition = extract_nutrition(nutrition_text)
    user_id = update.message.from_user.id

    if not nutrition:
        await update.message.reply_text("Не смог вытащить калории из ответа 😔 Попробуй ещё раз.")
        return

    cal, pr, fat, carb = nutrition

    add_food(user_id, cal, pr, fat, carb)
    day = get_day(user_id)

    friendly = coach_reply(nutrition_text, day)
    await update.message.reply_text(friendly)

    await update.message.reply_text(
        f"📊 Сегодня уже:\n"
        f"{round(day['calories'])} ккал\n"
        f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
    )


# -------- Фото --------
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Секунду, смотрю что у тебя на тарелке 👀")

    try:
        result = analyze_food(file_path)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог разобрать фото 😔 Попробуй ещё раз или напиши текстом.")


# -------- Текст --------
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""

    # фразы типа "убери апельсин" -> undo
    if is_undo_text(user_text):
        await undo_cmd(update, context)
        return

    await update.message.reply_text("Считаю...")

    try:
        result = analyze_text_food(user_text)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял 🤔 Напиши проще или отправь фото/голос.")


# -------- Голос --------
async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = await update.message.voice.get_file()
    file_path = "voice.ogg"
    await voice.download_to_drive(file_path)

    await update.message.reply_text("Слушаю... 🎧")

    try:
        text = transcribe_voice(file_path)
        # Если голосом сказал "убери/отмени" — тоже откат
        if is_undo_text(text):
            await undo_cmd(update, context)
            return

        result = analyze_text_food(text)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать голос 😔 Попробуй ещё раз.")


# -------- Запуск --------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("today", today_cmd))
app.add_handler(CommandHandler("undo", undo_cmd))
app.add_handler(CommandHandler("reset", reset_cmd))
app.add_handler(CommandHandler("want", want_cmd))
app.add_handler(CommandHandler("plan", plan_cmd))

app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.VOICE, voice_message))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

print("Bot started...")
app.run_polling()