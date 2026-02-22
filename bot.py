import os
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food
from voice_ai import transcribe_voice
from users_db import add_food, get_day, undo_last, reset_day

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")


# ---------- КЛАВИАТУРА ----------
main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📸 Добавить еду")],
        [KeyboardButton("📊 Сегодня"), KeyboardButton("↩️ Отменить")],
        [KeyboardButton("🍽 Что съесть"), KeyboardButton("⚙️ Профиль")]
    ],
    resize_keyboard=True
)


# ---------- ИЗВЛЕЧЕНИЕ БЖУ ----------
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


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я помогу вести питание 🍽\n\n"
        "Просто отправь фото, голос или напиши что съел.\n"
        "Можно пользоваться кнопками ниже 👇",
        reply_markup=main_keyboard
    )


# ---------- СЕГОДНЯ ----------
async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    day = get_day(user_id)

    await update.message.reply_text(
        "📊 За сегодня:\n"
        f"{round(day['calories'])} ккал\n"
        f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
    )


# ---------- UNDO ----------
async def undo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    day = undo_last(user_id)

    if not day:
        await update.message.reply_text("Пока нечего отменять 🙂")
        return

    await update.message.reply_text(
        "↩️ Убрал последний приём пищи\n\n"
        f"Теперь: {round(day['calories'])} ккал"
    )


# ---------- ДОБАВЛЕНИЕ ЕДЫ ----------
async def handle_nutrition(update: Update, nutrition_text: str):

    nutrition = extract_nutrition(nutrition_text)
    user_id = update.message.from_user.id

    if not nutrition:
        await update.message.reply_text("Не смог понять еду 😔 Попробуй иначе.")
        return

    cal, pr, fat, carb = nutrition

    add_food(user_id, cal, pr, fat, carb)
    day = get_day(user_id)

    await update.message.reply_text(
        f"Записал 🍳\n"
        f"+{round(cal)} ккал\n\n"
        f"Сегодня: {round(day['calories'])} ккал"
    )


# ---------- ФОТО ----------
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Секунду 👀")

    try:
        result = analyze_food(file_path)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял фото 😔")


# ---------- ТЕКСТ ----------
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    # кнопки
    if text == "📊 Сегодня":
        await today_cmd(update, context)
        return

    if text == "↩️ Отменить":
        await undo_cmd(update, context)
        return

    if text == "🍽 Что съесть":
        await update.message.reply_text(
            "Напиши что хочется:\n"
            "сладкое / сытное / лёгкое / белковое"
        )
        return

    if text == "⚙️ Профиль":
        await update.message.reply_text(
            "Скоро тут будет цель, вес и норма калорий 👤"
        )
        return

    # иначе считаем еду
    await update.message.reply_text("Считаю...")

    try:
        result = analyze_text_food(text)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял 😔 Попробуй проще.")


# ---------- ГОЛОС ----------
async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    voice = await update.message.voice.get_file()
    file_path = "voice.ogg"
    await voice.download_to_drive(file_path)

    await update.message.reply_text("Слушаю 🎧")

    try:
        text = transcribe_voice(file_path)
        result = analyze_text_food(text)
        await handle_nutrition(update, result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать голос 😔")


# ---------- ЗАПУСК ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.VOICE, voice_message))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

print("Bot started...")
app.run_polling()