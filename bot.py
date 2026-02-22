import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food
from voice_ai import transcribe_voice
from users_db import add_food, get_day
from coach_ai import coach_reply

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")


# -------- Извлечение БЖУ --------
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


# -------- /start --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я буду вести твой дневник питания 🍽\n\n"
        "Можешь:\n"
        "📸 отправить фото еды\n"
        "🎤 сказать голосом\n"
        "✍️ написать текстом\n\n"
        "Пример: «2 яйца и хлеб»"
    )


# -------- ФОТО --------
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Секунду, смотрю что у тебя на тарелке 👀")

    try:
        result = analyze_food(file_path)

        nutrition = extract_nutrition(result)
        user_id = update.message.from_user.id

        if nutrition:
            cal, pr, fat, carb = nutrition

            add_food(user_id, cal, pr, fat, carb)
            day = get_day(user_id)

            friendly = coach_reply(result, day)
            await update.message.reply_text(friendly)

            await update.message.reply_text(
                f"📊 Сегодня уже:\n"
                f"{round(day['calories'])} ккал\n"
                f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
            )

    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог разобрать фото 😔 Попробуй ещё раз или напиши текстом.")


# -------- ТЕКСТ --------
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_text = update.message.text
    await update.message.reply_text("Считаю...")

    try:
        result = analyze_text_food(user_text)

        nutrition = extract_nutrition(result)
        user_id = update.message.from_user.id

        if nutrition:
            cal, pr, fat, carb = nutrition

            add_food(user_id, cal, pr, fat, carb)
            day = get_day(user_id)

            friendly = coach_reply(result, day)
            await update.message.reply_text(friendly)

            await update.message.reply_text(
                f"📊 Сегодня уже:\n"
                f"{round(day['calories'])} ккал\n"
                f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
            )

    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял еду 🤔 Попробуй написать иначе.")


# -------- ГОЛОС --------
async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    voice = await update.message.voice.get_file()
    file_path = "voice.ogg"
    await voice.download_to_drive(file_path)

    await update.message.reply_text("Слушаю... 🎧")

    try:
        text = transcribe_voice(file_path)

        await update.message.reply_text(f"Ты сказал:\n{text}")

        result = analyze_text_food(text)

        nutrition = extract_nutrition(result)
        user_id = update.message.from_user.id

        if nutrition:
            cal, pr, fat, carb = nutrition

            add_food(user_id, cal, pr, fat, carb)
            day = get_day(user_id)

            friendly = coach_reply(result, day)
            await update.message.reply_text(friendly)

            await update.message.reply_text(
                f"📊 Сегодня уже:\n"
                f"{round(day['calories'])} ккал\n"
                f"Б: {round(day['protein'])} г | Ж: {round(day['fat'])} г | У: {round(day['carbs'])} г"
            )

    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать голос 😔 Попробуй ещё раз.")


# -------- ЗАПУСК --------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
app.add_handler(MessageHandler(filters.VOICE, voice_message))

print("Bot started...")
app.run_polling()