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

# ---------------- UI ----------------

MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Добавить еду")],
        [KeyboardButton("📊 Сегодня")],
        [KeyboardButton("🧠 Совет")],
    ],
    resize_keyboard=True,
)

CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ Записать", callback_data="save_food")],
        [InlineKeyboardButton("✏️ Исправить", callback_data="edit_food")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_food")],
    ]
)

ASK_NORM_KB = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Посчитать норму", callback_data="calc_norm")]]
)

SEX_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Мужской", callback_data="sex_m")],
        [InlineKeyboardButton("Женский", callback_data="sex_f")],
    ]
)

# ---------------- Helpers ----------------

def extract_kcal(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"(\d{2,5})\s*(ккал|kcal)", text.lower())
    return int(m.group(1)) if m else 0

def format_today(user_id: int) -> str:
    user = get_user(user_id)
    target = (user.get("profile", {}) or {}).get("kcal_target")
    summary = get_today_summary(user_id)
    total = int(summary.get("kcal_total", 0) or 0)

    if target:
        left = int(target) - total
        return f"Сегодня: {total} / {target} ккал\nОсталось: {left} ккал"
    return f"Сегодня съедено: {total} ккал"

async def reply_food_saved(chat, user_id: int, food_text: str, kcal: int):
    user = get_user(user_id)
    target = (user.get("profile", {}) or {}).get("kcal_target")
    summary = get_today_summary(user_id)

    if target:
        left = int(target) - int(summary["kcal_total"])
        await chat.send_message(
            f"{food_text}\n≈ {kcal} ккал\n\n"
            f"Сегодня: {summary['kcal_total']} / {target} ккал\n"
            f"Осталось: {left} ккал",
            reply_markup=MAIN_KB,
        )
    else:
        await chat.send_message(
            f"{food_text}\n≈ {kcal} ккал\n\n"
            f"Сегодня: {summary['kcal_total']} ккал",
            reply_markup=MAIN_KB,
        )

# ---------------- Start ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Привет, {user.first_name} 👋\n\n"
        "Я считаю калории.\n"
        "Нажми ➕ Добавить еду и отправь текст/фото/голос.\n"
        "📊 Сегодня покажет сумму и остаток (если есть норма).",
        reply_markup=MAIN_KB,
    )

# ---------------- Text ----------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    user_id = user.id
    text = (update.message.text or "").strip()
    state = context.user_data.get("state")

    # меню
    if text == "➕ Добавить еду":
        context.user_data["state"] = "waiting_food_any"
        await update.message.reply_text("Ок. Отправь что съел: текст / фото / голос.")
        return

    if text == "📊 Сегодня":
        user_obj = get_user(user_id)
        target = (user_obj.get("profile", {}) or {}).get("kcal_target")
        msg = format_today(user_id)

        if not target:
            await update.message.reply_text(
                msg + "\n\nХочешь — посчитаю твою норму.",
                reply_markup=ASK_NORM_KB,
            )
        else:
            await update.message.reply_text(msg, reply_markup=MAIN_KB)
        return

    if text == "🧠 Совет":
        context.user_data["state"] = "coach"
        await update.message.reply_text("Ок. Задай вопрос про питание.")
        return

    # анкета нормы
    if state == "ask_age":
        try:
            age = int(text)
        except:
            await update.message.reply_text("Возраст — числом. Например: 32")
            return
        context.user_data["age"] = age
        context.user_data["state"] = "ask_height"
        await update.message.reply_text("Рост (см)?")
        return

    if state == "ask_height":
        try:
            height = int(text)
        except:
            await update.message.reply_text("Рост — числом. Например: 180")
            return
        context.user_data["height"] = height
        context.user_data["state"] = "ask_weight"
        await update.message.reply_text("Вес (кг)?")
        return

    if state == "ask_weight":
        try:
            weight = float(text.replace(",", "."))
        except:
            await update.message.reply_text("Вес — числом. Например: 92 или 92.5")
            return

        sex = context.user_data.get("sex")
        age = context.user_data.get("age")
        height = context.user_data.get("height")

        if sex not in ("m", "f") or not age or not height:
            context.user_data["state"] = None
            await update.message.reply_text("Анкета сбилась. Нажми 📊 Сегодня → Посчитать норму.")
            return

        # Mifflin-St Jeor (простая версия) + лёгкий дефицит
        bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex == "m" else -161)
        target = int(bmr * 1.4 - 400)

        set_profile_field(user_id, "kcal_target", target)
        context.user_data["state"] = None

        await update.message.reply_text(
            f"Готово 👍\nТвоя дневная норма: ~{target} ккал\n"
            "Теперь буду показывать остаток в 📊 Сегодня и после приёмов пищи.",
            reply_markup=MAIN_KB,
        )
        return

    # коуч
    if state == "coach":
        reply = coach_chat(text)
        await update.message.reply_text(reply)
        return

    # еда текстом — считаем и записываем сразу
    # (если пользователь уже нажал “Добавить еду” ИЛИ просто написал еду без кнопок)
    if state == "waiting_food_any" or looks_like_food_text(text):
        analysis = analyze_text_food(text, {})
        kcal = extract_kcal(str(analysis))
        add_food_entry(user_id, text, kcal)
        context.user_data["state"] = None
        await reply_food_saved(update.effective_chat, user_id, text, kcal)
        return

    await update.message.reply_text("Нажми ➕ Добавить еду или 📊 Сегодня.", reply_markup=MAIN_KB)

def looks_like_food_text(text: str) -> bool:
    """
    Чтобы не требовать кнопку всегда, пытаемся распознать, что сообщение похоже на еду.
    Очень простое правило: есть цифра/кол-во или ключевые слова еды.
    """
    t = text.lower()
    if any(w in t for w in ["яйц", "куриц", "рис", "греч", "хлеб", "сыр", "мяс", "рыб", "суп", "паста", "карто", "салат", "йогур", "творог", "банан", "яблок", "шаур", "бургер", "пицц"]):
        return True
    if re.search(r"\b\d+\b", t):
        return True
    return False

# ---------------- Photo ----------------

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    user_id = user.id

    # если мы в коуче — не мешаем
    if context.user_data.get("state") == "coach":
        await update.message.reply_text("Я сейчас в режиме 🧠 Совет. Нажми ➕ Добавить еду для фото.")
        return

    # принимаем фото всегда (чтобы не было “не распознаёт”)
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()

    result = analyze_food(bytes(data))  # должен вернуть текст
    if not result:
        result = "Не смог определить еду на фото."

    context.user_data["last_food"] = str(result)
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Я вижу:\n{result}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ---------------- Voice ----------------

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    user_id = user.id

    if context.user_data.get("state") == "coach":
        await update.message.reply_text("Я сейчас в режиме 🧠 Совет. Нажми ➕ Добавить еду для голоса.")
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    data = await file.download_as_bytearray()

    text = transcribe_voice(bytes(data))
    if not text:
        text = "Не смог распознать голос."

    context.user_data["last_food"] = str(text)
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Распознал:\n{text}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ---------------- Callback ----------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    ensure_user(user.id, user.username or "")
    user_id = user.id

    data = query.data

    if data == "cancel_food":
        context.user_data["last_food"] = None
        context.user_data["state"] = None
        await query.message.reply_text("Ок 👍", reply_markup=MAIN_KB)
        return

    if data == "edit_food":
        context.user_data["state"] = "waiting_food_any"
        await query.message.reply_text("Ок. Напиши исправленный текст.")
        return

    if data == "save_food":
        food = context.user_data.get("last_food")
        if not food:
            await query.message.reply_text("Не вижу что сохранять. Нажми ➕ Добавить еду.")
            return

        analysis = analyze_text_food(str(food), {})
        kcal = extract_kcal(str(analysis))

        add_food_entry(user_id, str(food), kcal)
        context.user_data["state"] = None

        await query.message.reply_text("Записал 👍", reply_markup=MAIN_KB)
        await reply_food_saved(query.message.chat, user_id, str(food), kcal)
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

# ---------------- Main ----------------

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is missing in .env")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()