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

from users_db import (
    ensure_user,
    add_food_entry,
    get_today_summary,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ================== КЛАВИАТУРЫ ==================

MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🍽 Добавить еду"), KeyboardButton("💡 Совет")],
        [KeyboardButton("📊 Сегодня"), KeyboardButton("🔥 Привести тело в порядок")],
        [KeyboardButton("⚙️ Режим")],
    ],
    resize_keyboard=True,
)

ADD_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✍️ Текст", callback_data="add_text")],
        [InlineKeyboardButton("📷 Фото", callback_data="add_photo")],
        [InlineKeyboardButton("🎤 Голос", callback_data="add_voice")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")],
    ]
)

MODE_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("⚡ Просто считать калории", callback_data="mode_quick")],
        [InlineKeyboardButton("📈 План и статистика", callback_data="mode_plan")],
    ]
)

ADVICE_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🍫 Хочу сладкое", callback_data="adv_sweet")],
        [InlineKeyboardButton("🍗 Хочу сытное", callback_data="adv_hearty")],
        [InlineKeyboardButton("🥗 Хочу лёгкое", callback_data="adv_light")],
        [InlineKeyboardButton("💪 Добрать белок", callback_data="adv_protein")],
        [InlineKeyboardButton("🌙 Что на ужин", callback_data="adv_dinner")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="adv_question")],
    ]
)

CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ Записать", callback_data="save_food")],
        [InlineKeyboardButton("✏️ Исправить", callback_data="edit_food")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_food")],
    ]
)

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    context.user_data["mode"] = "quick"

    await update.message.reply_text(
        f"Привет, {user.first_name} 👋\n\n"
        "Я умею:\n"
        "• считать калории по фото, голосу и тексту\n"
        "• вести дневник питания\n"
        "• помогать без занудства\n\n"
        "Выбери действие:",
        reply_markup=MAIN_KB,
    )

    await update.message.reply_text(
        "Если захочешь — помогу привести тело в порядок: цель, контроль и подсказки.\n"
        "Кнопка ниже 👇",
        reply_markup=MAIN_KB,
    )

# ================== CALLBACK ==================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # ---- режимы
    if data == "mode_quick":
        context.user_data["mode"] = "quick"
        await query.message.reply_text("Ок 👍 Просто считаем калории.", reply_markup=MAIN_KB)
        return

    if data == "mode_plan":
        context.user_data["mode"] = "plan"
        await query.message.reply_text(
            "Включили режим плана 📈\nТеперь буду показывать остаток калорий за день.",
            reply_markup=MAIN_KB,
        )
        return

    # ---- добавление еды
    if data == "add_text":
        context.user_data["state"] = "wait_text_food"
        await query.message.reply_text("Напиши что съел. Например: яйца варёные 3 шт")
        return

    if data == "add_photo":
        context.user_data["state"] = "wait_photo_food"
        await query.message.reply_text("Пришли фото еды 📷")
        return

    if data == "add_voice":
        context.user_data["state"] = "wait_voice_food"
        await query.message.reply_text("Запиши голосом что съел 🎤")
        return

    # ---- подтверждение
    if data == "cancel_food":
        context.user_data.pop("last_food", None)
        await query.message.reply_text("Ок, отменил.", reply_markup=MAIN_KB)
        return

    if data == "edit_food":
        context.user_data["state"] = "edit_food"
        await query.message.reply_text("Исправь текст и отправь заново.")
        return

    if data == "save_food":
        food = context.user_data.get("last_food")
        if not food:
            await query.message.reply_text("Ошибка записи.")
            return

        analysis = analyze_text_food(food, {})
        kcal = extract_kcal(str(analysis))

        add_food_entry(update.effective_user.id, food, kcal)

        summary = get_today_summary(update.effective_user.id)

        if context.user_data.get("mode") == "quick":
            await query.message.reply_text(
                f"Записал ✅\nКалорий сегодня: {summary['kcal_total']}",
                reply_markup=MAIN_KB,
            )
        else:
            await query.message.reply_text(
                f"Записал ✅\nКалорий: {summary['kcal_total']} / {summary['kcal_target']}\n"
                f"Осталось: {summary['kcal_left']}",
                reply_markup=MAIN_KB,
            )

        await query.message.reply_text(
            "Хочешь привести тело в порядок системно? Жми 🔥 Привести тело в порядок",
            reply_markup=MAIN_KB,
        )
        return

    # ---- советы
    if data.startswith("adv_"):
        prompts = {
            "adv_sweet": "Хочу сладкое без срыва",
            "adv_hearty": "Хочу сытную еду, но без переедания",
            "adv_light": "Хочу лёгкую еду",
            "adv_protein": "Как добрать белок сегодня",
            "adv_dinner": "Что съесть на ужин",
        }

        if data == "adv_question":
            context.user_data["state"] = "ask_coach"
            await query.message.reply_text("Задай вопрос.")
            return

        reply = coach_chat(prompts[data])
        await query.message.reply_text(reply, reply_markup=ADVICE_KB)
        return

# ================== ТЕКСТ ==================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # кнопки
    if text == "🍽 Добавить еду":
        await update.message.reply_text("Как добавим?", reply_markup=ADD_KB)
        return

    if text == "💡 Совет":
        await update.message.reply_text("Чем помочь?", reply_markup=ADVICE_KB)
        return

    if text == "📊 Сегодня":
        summary = get_today_summary(update.effective_user.id)
        await update.message.reply_text(
            f"Калорий сегодня: {summary['kcal_total']}",
            reply_markup=MAIN_KB,
        )
        return

    if text == "🔥 Привести тело в порядок":
        await update.message.reply_text(
            "Отличное решение 💪\n"
            "Включи режим плана: ⚙️ Режим → План и статистика\n"
            "И начнём работать системно.",
            reply_markup=MAIN_KB,
        )
        return

    if text == "⚙️ Режим":
        await update.message.reply_text("Выбери режим:", reply_markup=MODE_KB)
        return

    # ---- ожидание еды
    if context.user_data.get("state") in ["wait_text_food", "edit_food"]:
        context.user_data["last_food"] = text
        context.user_data["state"] = None
        await update.message.reply_text(
            f"Хочу записать:\n{text}\n\nПодтверждаешь?",
            reply_markup=CONFIRM_KB,
        )
        return

    # ---- вопрос коучу
    if context.user_data.get("state") == "ask_coach":
        reply = coach_chat(text)
        context.user_data["state"] = None
        await update.message.reply_text(reply)
        return

# ================== ФОТО ==================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "wait_photo_food":
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()

    result = analyze_food(bytes(data))
    context.user_data["last_food"] = str(result)
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Я увидел:\n{result}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ================== ГОЛОС ==================

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "wait_voice_food":
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    data = await file.download_as_bytearray()

    text = transcribe_voice(bytes(data))
    context.user_data["last_food"] = text
    context.user_data["state"] = None

    await update.message.reply_text(
        f"Распознал так:\n{text}\n\nЗаписать?",
        reply_markup=CONFIRM_KB,
    )

# ================== Kcal ==================

def extract_kcal(text):
    m = re.search(r"(\\d{2,5})\\s*(ккал|kcal)", text.lower())
    return int(m.group(1)) if m else None

# ================== MAIN ==================

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