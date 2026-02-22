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

MODEL = "gpt-4o"
MAX_HISTORY = 12
MAX_TELEGRAM_LENGTH = 4000

SYSTEM_PROMPT = """
Ты персональный AI-нутрициолог.

Правила ответа:
- Кратко
- Без хештегов
- С умеренными эмодзи 🍳 🥗 🔥 💪 📊
- Структурировано
"""

user_sessions = {}

def trim_history(history):
    if len(history) > MAX_HISTORY:
        return [history[0]] + history[-MAX_HISTORY:]
    return history

async def send_long_message(update, text):
    for i in range(0, len(text), MAX_TELEGRAM_LENGTH):
        await update.message.reply_text(text[i:i + MAX_TELEGRAM_LENGTH])

# ---------------- GPT CORE ----------------

async def process_text(update, user_text):

    user_id = update.effective_user.id

    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    user_sessions[user_id].append({"role": "user", "content": user_text})
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

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "GPT-нутрициолог запущен 👌\n\nПиши, отправляй фото или голос 🎙"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_text(update, update.message.text)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

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

    reply = response.output_text.replace("#", "")
    await send_long_message(update, reply)

# 🔥 ВОТ НОВОЕ — ГОЛОС

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    voice = update.message.voice
    file = await voice.get_file()
    voice_bytes = await file.download_as_bytearray()

    # сохраняем временно
    with open("voice.ogg", "wb") as f:
        f.write(voice_bytes)

    # расшифровка
    with open("voice.ogg", "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )

    text = transcript.text

    await update.message.reply_text(f"🎙 Распознано:\n{text}")

    await process_text(update, text)

# ---------------- RUN ----------------

if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("PRO GPT Бот запущен 🚀")
    app.run_polling()