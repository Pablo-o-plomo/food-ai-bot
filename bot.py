import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")


# -------- СТАРТ --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я — AI нутрициолог.\n\n"
        "Можешь:\n"
        "📸 отправить фото еды\n"
        "✍️ написать что съел\n\n"
        "Например:\n"
        "«2 яйца и тост»\n"
        "«курица 200 г и рис»"
    )


# -------- ФОТО --------
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Анализирую фото... 👨‍🍳")

    try:
        result = analyze_food(file_path)
        await update.message.reply_text(result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать фото 😔 Попробуй ещё раз или опиши текстом.")


# -------- ТЕКСТ --------
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_text = update.message.text

    await update.message.reply_text("Считаю...")

    try:
        result = analyze_text_food(user_text)
        await update.message.reply_text(result)
    except Exception as e:
        print(e)
        await update.message.reply_text("Не понял еду 🤔 Попробуй написать проще.")


# -------- ЗАПУСК --------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

app.run_polling()