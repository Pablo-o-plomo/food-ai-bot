import os
import re
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from coach_ai import coach_chat
from vision import analyze_food
from food_text_ai import analyze_text_food
from voice_ai import transcribe_voice

from users_db import ensure_user, add_food_entry, get_today_summary, set_profile_field, get_user

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- КЛАВИАТУРЫ ----------------

MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Добавить еду")],
        [KeyboardButton("📊 Сегодня")],
        [KeyboardButton("🧠 Совет")],
    ],
    resize_keyboard=True,
)

ADD_METHOD_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("📷 Фото", callback_data="food_photo")],
    [InlineKeyboardButton("🎤 Голос", callback_data="food_voice")],
    [InlineKeyboardButton("✍️ Текст", callback_data="food_text")],
])

CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ Записать", callback_data="save_food")],
        [InlineKeyboardButton("✏️ Исправить", callback_data="edit_food")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_food")],
    ]
)

ASK_NORM_KB = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Посчитать мою норму", callback_data="calc_norm")]]
)

SEX_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Мужской", callback_data="sex_m")],
    [InlineKeyboardButton("Женский", callback_data="sex_f")],
])

# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")

    context.user_data["state"] = None

    await update.message.reply_text(
        f"Привет, {user.first_name} 👋\n"
        "Я считаю калории.\n"
        "Нажми ➕ Добавить еду и отправь фото, голос или текст.",
        reply_markup=MAIN_KB,
    )

# ---------------- ТЕКСТ ----------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    state = context.user_data.get("state")

    # меню
    if text == "➕ Добавить еду":
        context.user_data["state"] = None
        await update.message.reply_text("Как добавим?", reply_markup=ADD_METHOD_KB)
        return

    if text == "📊 Сегодня":
        user = get_user(user_id)
        profile = user.get("profile", {})
        target = profile.get("kcal_target")
        summary = get_today_summary(user_id)

        if not target:
            await update.message.reply_text(
                f"Сегодня съедено: {summary['kcal_total']} ккал\n\n"
                "Хочешь — посчитаю твою норму.",
                reply_markup=ASK_NORM_KB,
            )
            return

        left = target - summary["kcal_total"]
        await update.message.reply_text(
            f"Сегодня: {summary['kcal_total']} / {target} ккал\n"
            f"Осталось: {left} ккал",
            reply_markup=MAIN_KB,
        )
        return

    if text == "🧠 Совет":
        context.user_data["state"] = "coach"
        await update.message.reply_text("Спроси любой вопрос про питание.")
        return

    # коуч
    if state == "coach":
        reply = coach_chat(text)
        await update.message.reply_text(reply)
        return

    # ---- ТЕКСТ ЕДА (СРАЗУ СЧИТАЕМ) ----
    if state == "waiting_food_text":
        analysis = analyze_text_food(text, {})
        kcal = extract_kcal(str(analysis))

        add_food_entry(user_id, text, kcal)
        context.user_data["state"] = None

        user = get_user(user_id)
        target = user.get("profile", {}).get("kcal_target")
        summary = get_today_summary(user_id)

        if target:
            left = target - summary["kcal_total"]
            await update.message.reply_text(
                f"{text}\n≈ {kcal} ккал\n\n"
                f"Сегодня: {summary['kcal_total']} / {target} ккал\n"
                f"Осталось: {left} ккал",
                reply_markup=MAIN_KB,
            )
        else:
            await update.message.reply_text(
                f"{text}\n≈ {kcal} ккал\n\n"
                f"Сегодня: {summary['kcal_total']} ккал",
                reply_markup=MAIN_KB,
            )
        return

    # ---- АНКЕТА НОРМЫ ----
    if state == "ask_age":
        context.user_data["age"] = int(text)
        context.user_data["state"] = "ask_height"
        await update.message.reply_text("Рост (см)?")
        return

    if state == "ask_height":
        context.user_data["height"] = int(text)
        context.user_data["state"] = "ask_weight"
        await update.message.reply_text("Вес (кг)?")
        return

    if state == "ask_weight":
        weight = float(text)
        age = context.user_data["age"]
        height = context.user_data["height"]
        sex = context.user_data["sex"]

        bmr = 10*weight + 6.25*height - 5*age + (5 if sex=="m" else -161)
        target = int(bmr*1.4 - 400)

        set_profile_field(user_id, "kcal_target", target)
        context.user_data["state"] = None

        await update.message.reply_text(
            f"Твоя норма: ~{target} ккал/день\nТеперь буду показывать остаток 👍",
            reply_markup=MAIN_KB,
        )

# ---------------- ФОТО ----------------

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "waiting_photo":
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()

    result = analyze_food(bytes(data))
    context.user_data["last_food"] = result
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Я вижу:\n{result}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ---------------- ГОЛОС ----------------

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "waiting_voice":
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    data = await file.download_as_bytearray()

    text = transcribe_voice(bytes(data))
    context.user_data["last_food"] = text
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Распознал:\n{text}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ---------------- CALLBACK ----------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "food_text":
        context.user_data["state"] = "waiting_food_text"
        await query.message.reply_text("Напиши что съел.")
        return

    if data == "food_photo":
        context.user_data["state"] = "waiting_photo"
        await query.message.reply_text("Пришли фото еды.")
        return

    if data == "food_voice":
        context.user_data["state"] = "waiting_voice"
        await query.message.reply_text("Запиши голосом что съел.")
        return

    if data == "cancel_food":
        context.user_data["state"] = None
        await query.message.reply_text("Ок 👍", reply_markup=MAIN_KB)
        return

    if data == "edit_food":
        context.user_data["state"] = "waiting_food_text"
        await query.message.reply_text("Исправь и отправь заново.")
        return

    if data == "save_food":
        food = context.user_data.get("last_food")
        analysis = analyze_text_food(food, {})
        kcal = extract_kcal(str(analysis))

        add_food_entry(user_id, food, kcal)
        context.user_data["state"] = None

        summary = get_today_summary(user_id)
        await query.message.reply_text(
            f"Записал 👍\nСегодня: {summary['kcal_total']} ккал",
            reply_markup=MAIN_KB,
        )
        return

    if data == "calc_norm":
        context.user_data["state"] = "ask_sex"
        await query.message.reply_text("Выбери пол:", reply_markup=SEX_KB)
        return

    if data == "sex_m":
        context.user_data["sex"] = "m"
        context.user_data["state"] = "ask_age"
        await query.message.reply_text("Возраст?")
        return

    if data == "sex_f":
        context.user_data["sex"] = "f"
        context.user_data["state"] = "ask_age"
        await query.message.reply_text("Возраст?")
        return

# ---------------- УТИЛИТА ----------------

def extract_kcal(text):
    m = re.search(r"(\d{2,5})\s*(ккал|kcal)", text.lower())
    return int(m.group(1)) if m else 0

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()