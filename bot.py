import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from vision import analyze_food

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\nЯ считаю калории по фото еды.\nОтправь фото тарелки 🍽"
    )

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("Анализирую еду...")

    try:
        result = analyze_food(file_path)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text("Не смог распознать фото 😢 Попробуй ещё раз.")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))

print("Бот запускается...")
app.run_polling()