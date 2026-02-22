import os
import base64
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
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

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 План на день")],
        [KeyboardButton("🧮 Подсчитать калории")],
    ],
    resize_keyboard=True,
)

# ---------------- PLAN ----------------

def generate_plan(goal, weight, height, activity):

    prompt = f"""
    Составь план питания на 1 день.
    Цель: {goal}
    Вес: {weight} кг
    Рост: {height} см
    Активность: {activity}
    """

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        max_output_tokens=500,
    )

    return response.output_text


# ---------------- CALORIES TEXT ----------------

def calculate_calories(text):

    prompt = f"""
    Определи калорийность и БЖУ блюда:
    {text}

    Ответь:
    Калории: ...
    Белки: ...
    Жиры: ...
    Углеводы: ...
    """

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        max_output_tokens=300,
    )

    return response.output_text


# ---------------- CALORIES PHOTO ----------------

def analyze_food_image(image_bytes):

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Определи блюдо и напиши калории и БЖУ."
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{b64_image}"
                    },
                ],
            }
        ],
        max_output_tokens=300,
    )

    return response.output_text


# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот питания запущен 👌",
        reply_markup=main_keyboard,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "📅 План на день":
        await update.message.reply_text("Цель? (похудение / набор / поддержание)")
        context.user_data["state"] = "goal"
        return

    if context.user_data.get("state") == "goal":
        context.user_data["goal"] = text
        await update.message.reply_text("Вес?")
        context.user_data["state"] = "weight"
        return

    if context.user_data.get("state") == "weight":
        context.user_data["weight"] = text
        await update.message.reply_text("Рост?")
        context.user_data["state"] = "height"
        return

    if context.user_data.get("state") == "height":
        context.user_data["height"] = text
        await update.message.reply_text("Активность?")
        context.user_data["state"] = "activity"
        return

    if context.user_data.get("state") == "activity":

        plan = generate_plan(
            context.user_data["goal"],
            context.user_data["weight"],
            context.user_data["height"],
            text,
        )

        await update.message.reply_text("Составляю план...")
        await update.message.reply_text(plan)

        context.user_data.clear()
        return

    if text == "🧮 Подсчитать калории":
        await update.message.reply_text("Отправь текст или фото блюда")
        return

    # если просто текст блюда
    result = calculate_calories(text)
    await update.message.reply_text(result)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo = update.message.photo[-1]
    file = await photo.get_file()

    image_bytes = await file.download_as_bytearray()

    await update.message.reply_text("Анализирую фото...")

    result = analyze_food_image(image_bytes)

    await update.message.reply_text(result)


if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Бот запущен 🚀")
    app.run_polling()