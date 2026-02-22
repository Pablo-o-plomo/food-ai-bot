import os
import base64
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

# ---------------- SETTINGS ----------------

MODEL = "gpt-4o"
MAX_HISTORY = 12
MAX_TELEGRAM_LENGTH = 4000

# ---------------- SYSTEM PROMPT ----------------

SYSTEM_PROMPT = """
Ты персональный AI-нутрициолог.

Правила ответа:
- Пиши кратко (до 1000 символов)
- Без хештегов
- Без лишней воды
- Структурировано
- Используй умеренные эмодзи (🍳 🥗 🔥 💪 📊)
- Делай переносы строк
- Не делай огромных абзацев

Формат:
Заголовок
Краткий разбор
Чёткие цифры
"""

# ---------------- MEMORY ----------------

user_sessions = {}

def trim_history(history):
    if len(history) > MAX_HISTORY:
        return [history[0]] + history[-MAX_HISTORY:]
    return history

# ---------------- UTIL ----------------

async def send_long_message(update, text):
    for i in range(0, len(text), MAX_TELEGRAM_LENGTH):
        await update.message.reply_text(text[i:i + MAX_TELEGRAM_LENGTH])

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "GPT-нутрициолог запущен 👌\n\nНапиши сообщение или отправь фото еды 🍽"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        user_id = update.effective_user.id
        text = update.message.text

        if user_id not in user_sessions:
            user_sessions[user_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

        user_sessions[user_id].append({"role": "user", "content": text})
        user_sessions[user_id] = trim_history(user_sessions[user_id])

        response = client.chat.completions.create(
            model=MODEL,
            messages=user_sessions[user_id],
            temperature=0.6,
            max_tokens=600,
        )

        reply = response.choices[0].message.content
        reply = reply.replace("#", "")

        user_sessions[user_id].append({"role": "assistant", "content": reply})
        user_sessions[user_id] = trim_history(user_sessions[user_id])

        await send_long_message(update, reply)

    except Exception as e:
        print("TEXT ERROR:", e)
        await update.message.reply_text("Произошла ошибка обработки запроса ⚠️")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_bytes = await file.download_as_bytearray()

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Проанализируй фото еды."},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{b64_image}",
                        },
                    ],
                },
            ],
            max_output_tokens=500,
        )

        reply = response.output_text
        reply = reply.replace("#", "")

        await send_long_message(update, reply)

    except Exception as e:
        print("PHOTO ERROR:", e)
        await update.message.reply_text("Ошибка анализа фото ⚠️")

# ---------------- RUN ----------------

if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("PRO GPT Бот запущен 🚀")
    app.run_polling()