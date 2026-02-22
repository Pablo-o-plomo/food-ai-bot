# ===================== IMPORTS =====================
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

from users_db import ensure_user, add_food_entry, get_today_summary, set_profile_field

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ===================== KEYBOARDS =====================

MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🍽 Добавить еду"), KeyboardButton("💡 Совет")],
        [KeyboardButton("📊 Сегодня"), KeyboardButton("⚖️ Взвешивание")],
        [KeyboardButton("⚙️ Режим")],
    ],
    resize_keyboard=True,
)

ADD_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✍️ Текст", callback_data="add_text")],
        [InlineKeyboardButton("📷 Фото", callback_data="add_photo")],
        [InlineKeyboardButton("🎤 Голос", callback_data="add_voice")],
    ]
)

MODE_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("⚡ Просто считать калории", callback_data="mode_quick")],
        [InlineKeyboardButton("📈 План и статистика", callback_data="mode_plan")],
    ]
)

CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ Записать", callback_data="save_food")],
        [InlineKeyboardButton("✏️ Исправить", callback_data="edit_food")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_food")],
    ]
)

# ===================== START =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    context.user_data["mode"] = "quick"

    await update.message.reply_text(
        f"Привет, {user.first_name} 👋\n\n"
        "Я помощник по питанию:\n"
        "• считаю калории по фото, тексту и голосу\n"
        "• веду дневник\n"
        "• могу помочь привести форму в порядок\n\n"
        "Выбери действие:",
        reply_markup=MAIN_KB,
    )

# ===================== РАСЧЁТ КАЛОРИЙ =====================

def calculate_calories(sex, weight, height, age, activity):
    # Mifflin-St Jeor
    bmr = 10*weight + 6.25*height - 5*age + (5 if sex=="m" else -161)

    factors = {
        "1":1.2,
        "2":1.375,
        "3":1.55,
        "4":1.725,
        "5":1.9
    }
    tdee = bmr * factors.get(activity,1.2)

    deficit = int(tdee - 500)
    return int(tdee), deficit

# ===================== CALLBACK =====================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # -------- РЕЖИМЫ --------
    if data == "mode_quick":
        context.user_data["mode"] = "quick"
        await query.message.reply_text("Ок. Просто считаем калории 👍", reply_markup=MAIN_KB)
        return

    if data == "mode_plan":
        context.user_data["mode"] = "plan"
        context.user_data["state"] = "ask_sex"
        await query.message.reply_text("Пол? Напиши m (муж) или f (жен)")
        return

    # -------- ДОБАВЛЕНИЕ ЕДЫ --------
    if data == "add_text":
        context.user_data["state"] = "wait_text_food"
        await query.message.reply_text("Напиши что съел.")
        return

    if data == "save_food":
        food = context.user_data.get("last_food")
        analysis = analyze_text_food(food,{})
        kcal = extract_kcal(str(analysis))
        add_food_entry(update.effective_user.id, food, kcal)
        summary = get_today_summary(update.effective_user.id)

        await query.message.reply_text(
            f"Записал ✅\nКалории сегодня: {summary['kcal_total']}",
            reply_markup=MAIN_KB,
        )
        return

# ===================== ТЕКСТ =====================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # кнопки
    if text == "🍽 Добавить еду":
        await update.message.reply_text("Как добавим?", reply_markup=ADD_KB)
        return

    if text == "⚙️ Режим":
        await update.message.reply_text("Выбери режим:", reply_markup=MODE_KB)
        return

    # ----- АНКЕТА -----
    if context.user_data.get("state") == "ask_sex":
        context.user_data["sex"] = text.lower()
        context.user_data["state"] = "ask_age"
        await update.message.reply_text("Возраст?")
        return

    if context.user_data.get("state") == "ask_age":
        context.user_data["age"] = int(text)
        context.user_data["state"] = "ask_height"
        await update.message.reply_text("Рост (см)?")
        return

    if context.user_data.get("state") == "ask_height":
        context.user_data["height"] = int(text)
        context.user_data["state"] = "ask_weight"
        await update.message.reply_text("Вес (кг)?")
        return

    if context.user_data.get("state") == "ask_weight":
        context.user_data["weight"] = float(text)
        context.user_data["state"] = "ask_activity"
        await update.message.reply_text(
            "Активность?\n"
            "1 — почти нет\n"
            "2 — 1-3 тренировки\n"
            "3 — 3-5\n"
            "4 — 6-7\n"
            "5 — очень высокая"
        )
        return

    if context.user_data.get("state") == "ask_activity":
        sex = context.user_data["sex"]
        age = context.user_data["age"]
        height = context.user_data["height"]
        weight = context.user_data["weight"]

        tdee, deficit = calculate_calories(sex, weight, height, age, text)

        set_profile_field(update.effective_user.id,"kcal_target",deficit)

        context.user_data["state"] = None

        await update.message.reply_text(
            f"Готово ✅\n\n"
            f"Поддержание: ~{tdee} ккал\n"
            f"Для снижения веса: {deficit} ккал/день\n\n"
            f"Теперь я буду считать остаток калорий и вести тебя.",
            reply_markup=MAIN_KB,
        )
        return

# ===================== UTIL =====================

def extract_kcal(text):
    m = re.search(r"(\\d{2,5})\\s*(ккал|kcal)", text.lower())
    return int(m.group(1)) if m else None

# ===================== MAIN =====================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()