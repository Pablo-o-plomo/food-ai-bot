import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food
from users_db import add_food, get_day

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")


# ---------- Извлечение БЖУ из ответа AI ----------
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


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я — AI нутрициолог и веду твой дневник питания.\n\n"
        "Ты можешь:\n"
        "📸 отправить фото еды\n"
        "✍️ написать что съел\n\n"
        "Примеры:\n"
        "«2 яйца и хлеб»\n"
        "«курица 200 г и рис»"
    )


# ---------- Фото ----------
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Анализирую фото... 👨‍🍳")

    try:
        result = analyze_food(file_path)
        await update.message.reply_text(result)

        nutrition = extract_nutrition(result)
        if nutrition:
            cal, pr, fat, carb = nutrition
            user_id = update.message.from_user.id

            add_food(user_id, cal, pr, fat, carb)
            day = get_day(user_id)

            await update.message.reply_text(
                f"📊 Записал в дневник!\n\n"
                f"Сегодня съедено:\n"
                f"Калории: {round(day['calories'])} ккал\n"
                f"Белки: {round(day['protein'])} г\n"
                f"Жиры: {round(day['fat'])} г\n"
                f"Углеводы: {round(day['carbs'])} г"
            )

    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать фото 😔 Попробуй ещё раз или опиши текстом.")


# ---------- Текст ----------
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_text = update.message.text

    await update.message.reply_text("Считаю...")

    try:
        result = analyze_text_food(user_text)
        await update.message.reply_text(result)

        nutrition = extract_nutrition(result)
        if nutrition:
            cal, pr, fat, carb = nutrition
            user_id = update.message.from_user.id

            add_food(user_id, cal, pr, fat, carb)
            day = get_day(user_id)

            await update.message.reply_text(
                f"📊 Записал в дневник!\n\n"
                f"Сегодня съедено:\n"
                f"Калории: {round(day['calories'])} ккал\n"
                f"Белки: {round(day['protein'])} г\n"
                f"Жиры: {round(day['fat'])} г\n"
                f"Углеводы: {round(day['carbs'])} г"
            )

    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял еду 🤔 Попробуй написать проще.")


# ---------- Запуск ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

print("Bot started...")
app.run_polling()