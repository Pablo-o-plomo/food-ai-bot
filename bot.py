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
MAX_HISTORY = 12  # ограничение памяти диалога

# ---------------- MEMORY ----------------

user_sessions = {}

SYSTEM_PROMPT = """
Ты персональный AI-нутрициолог и коуч.
Ты умеешь:
- составлять план питания
- считать калории
- анализировать фото еды
- помогать в похудении
- давать структурированные ответы

Отвечай понятно, структурировано и профессионально.
"""

# ---------------- UTIL ----------------

def trim_history(history):
    if len(history) > MAX_HISTORY:
        return [history[0]] + history[-MAX_HISTORY:]
    return history

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "GPT-нутрициолог запущен 👌\nНапиши что угодно или отправь фото еды."
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
            temperature=0.7,
        )

        reply = response.choices[0].message.content

        user_sessions[user_id].append({"role": "assistant", "content": reply})
        user_sessions[user_id] = trim_history(user_sessions[user_id])

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("Ошибка обработки запроса.")
        print("TEXT ERROR:", e)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_bytes = await file.download_as_bytearray()

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        response = client.responses.create(
            model="gpt-4.1",
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
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

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("Ошибка анализа фото.")
        print("PHOTO ERROR:", e)


# ---------------- RUN ----------------

if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("PRO GPT Бот запущен 🚀")
    app.run_polling()