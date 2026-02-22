import os
import re
from typing import Optional

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
    get_user,
    set_profile_field,
    add_food_entry,
    get_today_summary,
    profile_is_complete,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------- UI ----------
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🍽 Добавить еду"), KeyboardButton("💡 Совет")],
        [KeyboardButton("📊 Сегодня"), KeyboardButton("⚙️ Профиль")],
    ],
    resize_keyboard=True,
)

ADD_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✍️ Текст", callback_data="add:text")],
        [InlineKeyboardButton("📷 Фото", callback_data="add:photo")],
        [InlineKeyboardButton("🎤 Голос", callback_data="add:voice")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
    ]
)

ADVICE_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🍫 Хочу сладкое", callback_data="adv:sweet")],
        [InlineKeyboardButton("🍗 Хочу сытное", callback_data="adv:hearty")],
        [InlineKeyboardButton("🥗 Хочу лёгкое", callback_data="adv:light")],
        [InlineKeyboardButton("💪 Добрать белок", callback_data="adv:protein")],
        [InlineKeyboardButton("🌙 Что на ужин", callback_data="adv:dinner")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="adv:question")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
    ]
)

# ---------- States ----------
S_NONE = "none"
S_PROFILE_AGE = "profile_age"
S_PROFILE_SEX = "profile_sex"
S_PROFILE_HEIGHT = "profile_height"
S_PROFILE_WEIGHT = "profile_weight"
S_PROFILE_KCAL = "profile_kcal"

S_ADD_TEXT = "add_text"
S_ADD_PHOTO = "add_photo"
S_ADD_VOICE = "add_voice"

S_CONFIRM = "confirm"        # confirm last recognized text
S_EDIT = "edit"              # user edits recognized text

S_ADVICE_ASK = "advice_ask"  # user asks custom question


def _set_state(ctx: ContextTypes.DEFAULT_TYPE, state: str):
    ctx.user_data["state"] = state


def _get_state(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("state", S_NONE)


def _needs_profile(user_id: int) -> bool:
    return not profile_is_complete(user_id)


async def _go_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _set_state(ctx, S_NONE)
    text = "Главное меню."
    if update.message:
        await update.message.reply_text(text, reply_markup=MAIN_KB)
    else:
        await update.effective_chat.send_message(text, reply_markup=MAIN_KB)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")
    await update.message.reply_text(
        "Food AI Bot запущен.\nВыбирай действие:",
        reply_markup=MAIN_KB,
    )


# ---------- Profile flow ----------
async def _start_profile_flow(chat, ctx):
    _set_state(ctx, S_PROFILE_AGE)
    await chat.send_message("Сначала заполним профиль.\nСколько тебе лет? (числом, например 32)")


async def _profile_step(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if handled as profile step."""
    user_id = update.effective_user.id
    st = _get_state(ctx)
    text = (update.message.text or "").strip()

    if st == S_PROFILE_AGE:
        if not text.isdigit():
            await update.message.reply_text("Возраст — числом. Например: 32")
            return True
        set_profile_field(user_id, "age", int(text))
        _set_state(ctx, S_PROFILE_SEX)
        await update.message.reply_text("Пол? Напиши: m (муж) или f (жен)")
        return True

    if st == S_PROFILE_SEX:
        t = text.lower()
        if t not in ("m", "f"):
            await update.message.reply_text("Только m или f.")
            return True
        set_profile_field(user_id, "sex", t)
        _set_state(ctx, S_PROFILE_HEIGHT)
        await update.message.reply_text("Рост в см? Например: 180")
        return True

    if st == S_PROFILE_HEIGHT:
        if not text.isdigit():
            await update.message.reply_text("Рост — числом. Например: 180")
            return True
        set_profile_field(user_id, "height", int(text))
        _set_state(ctx, S_PROFILE_WEIGHT)
        await update.message.reply_text("Вес в кг? Например: 92")
        return True

    if st == S_PROFILE_WEIGHT:
        m = re.match(r"^\d+([.,]\d+)?$", text)
        if not m:
            await update.message.reply_text("Вес — числом. Например: 92 или 92.5")
            return True
        set_profile_field(user_id, "weight", float(text.replace(",", ".")))
        _set_state(ctx, S_PROFILE_KCAL)
        await update.message.reply_text("Цель по калориям в день? Например: 2000")
        return True

    if st == S_PROFILE_KCAL:
        if not text.isdigit():
            await update.message.reply_text("Калории — числом. Например: 2000")
            return True
        set_profile_field(user_id, "kcal_target", int(text))
        _set_state(ctx, S_NONE)
        await update.message.reply_text("Готово ✅ Профиль заполнен.", reply_markup=MAIN_KB)

        # if we had pending food text -> continue
        pending = ctx.user_data.pop("pending_food_text", None)
        if pending:
            await update.message.reply_text("Продолжаем запись еды. Что распознано:")
            await _show_confirm(update, ctx, pending)

        return True

    return False


# ---------- Confirm / edit flow ----------
def _confirm_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Записать", callback_data="cf:save")],
            [InlineKeyboardButton("✏️ Исправить", callback_data="cf:edit")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cf:cancel")],
        ]
    )


async def _show_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE, recognized_text: str):
    ctx.user_data["last_food_text"] = recognized_text
    _set_state(ctx, S_CONFIRM)
    await update.message.reply_text(
        f"Я распознал и хочу записать вот это:\n\n**{recognized_text}**\n\nПодтверждаешь?",
        reply_markup=_confirm_kb(),
        parse_mode="Markdown",
    )


def _extract_kcal(analysis_text: str) -> Optional[int]:
    """
    Пытаемся вытащить калории из ответа analyze_text_food.
    Если в твоём analyze_text_food другой формат — скажешь, я подстрою.
    """
    # варианты: "Калории: 340", "340 ккал", "≈ 340 ккал"
    m = re.search(r"(\d{2,5})\s*(ккал|kcal)", analysis_text.lower())
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    m2 = re.search(r"калор(ий|ии|ий)\s*[:\-]?\s*(\d{2,5})", analysis_text.lower())
    if m2:
        try:
            return int(m2.group(2))
        except:
            return None
    return None


# ---------- Callback handler ----------
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    ensure_user(user.id, user.username or "")

    data = query.data or ""

    # Navigation
    if data == "nav:home":
        _set_state(ctx, S_NONE)
        await query.message.reply_text("Главное меню.", reply_markup=MAIN_KB)
        return

    # Add food menu
    if data == "add:text":
        if _needs_profile(user.id):
            ctx.user_data["pending_food_text"] = None
            await _start_profile_flow(query.message.chat, ctx)
            return
        _set_state(ctx, S_ADD_TEXT)
        await query.message.reply_text("Напиши, что съел(а). Например: `яйца варёные 3 шт`", parse_mode="Markdown")
        return

    if data == "add:photo":
        if _needs_profile(user.id):
            await _start_profile_flow(query.message.chat, ctx)
            return
        _set_state(ctx, S_ADD_PHOTO)
        await query.message.reply_text("Ок. Пришли фото еды 📷")
        return

    if data == "add:voice":
        if _needs_profile(user.id):
            await _start_profile_flow(query.message.chat, ctx)
            return
        _set_state(ctx, S_ADD_VOICE)
        await query.message.reply_text("Ок. Запиши голосом, что съел 🎤")
        return

    # Advice menu
    if data.startswith("adv:"):
        key = data.split(":", 1)[1]

        if key == "question":
            _set_state(ctx, S_ADVICE_ASK)
            await query.message.reply_text("Ок. Задай вопрос.")
            return

        prompts = {
            "sweet": "Хочу сладкое. Дай вариант без срыва: 2-3 опции и что выбрать прямо сейчас.",
            "hearty": "Хочу сытное. Дай варианты плотного приема пищи, но в дефиците.",
            "light": "Хочу лёгкое. Дай варианты лёгкого блюда/перекуса.",
            "protein": "Надо добрать белок. Дай 3 варианта и порции.",
            "dinner": "Что на ужин сегодня? Дай 3 варианта и порции.",
        }
        prompt = prompts.get(key, "Дай совет по питанию.")
        reply = coach_chat(prompt)
        await query.message.reply_text(reply, reply_markup=ADVICE_KB)
        return

    # Confirm / edit / cancel
    if data == "cf:cancel":
        ctx.user_data.pop("last_food_text", None)
        _set_state(ctx, S_NONE)
        await query.message.reply_text("Ок, отменил.", reply_markup=MAIN_KB)
        return

    if data == "cf:edit":
        _set_state(ctx, S_EDIT)
        last = ctx.user_data.get("last_food_text", "")
        await query.message.reply_text(f"Исправь текст и отправь заново.\nТекущее: {last}")
        return

    if data == "cf:save":
        text = ctx.user_data.get("last_food_text")
        if not text:
            await query.message.reply_text("Не вижу что сохранять. Попробуй ещё раз.", reply_markup=MAIN_KB)
            _set_state(ctx, S_NONE)
            return

        # Analyze text -> kcal
        analysis = analyze_text_food(text, get_user(user.id).get("profile", {}))
        kcal = _extract_kcal(str(analysis))

        add_food_entry(user.id, text=text, kcal=kcal)

        summ = get_today_summary(user.id)
        entries = summ["entries"]
        last_line = entries[-1]["text"] if entries else text

        await query.message.reply_text(
            f"Записал ✅\n\nПоследнее: {last_line}\n"
            f"Ккал сегодня: {summ['kcal_total']} / {summ['kcal_target']}\n"
            f"Осталось: {summ['kcal_left']}",
            reply_markup=MAIN_KB,
        )
        _set_state(ctx, S_NONE)
        return


# ---------- Text / photo / voice messages ----------
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")

    # profile steps first
    if await _profile_step(update, ctx):
        return

    st = _get_state(ctx)
    text = (update.message.text or "").strip()

    # Main buttons
    if text == "🍽 Добавить еду":
        await update.message.reply_text("Как добавим?", reply_markup=ADD_KB)
        return

    if text == "💡 Совет":
        await update.message.reply_text("Чем помочь?", reply_markup=ADVICE_KB)
        return

    if text == "📊 Сегодня":
        summ = get_today_summary(user.id)
        lines = [f"• {e['text']}" for e in summ["entries"][-10:]] or ["— пока пусто —"]
        await update.message.reply_text(
            "Сегодня:\n" + "\n".join(lines) +
            f"\n\nКкал: {summ['kcal_total']} / {summ['kcal_target']} (осталось {summ['kcal_left']})",
            reply_markup=MAIN_KB,
        )
        return

    if text == "⚙️ Профиль":
        u = get_user(user.id)
        p = u.get("profile", {})
        await update.message.reply_text(
            "Профиль:\n"
            f"Возраст: {p.get('age')}\n"
            f"Пол: {p.get('sex')}\n"
            f"Рост: {p.get('height')}\n"
            f"Вес: {p.get('weight')}\n"
            f"Цель ккал: {p.get('kcal_target')}\n\n"
            "Хочешь обновить? Напиши: /profile",
            reply_markup=MAIN_KB,
        )
        return

    # Advice custom question
    if st == S_ADVICE_ASK:
        reply = coach_chat(text)
        await update.message.reply_text(reply, reply_markup=ADVICE_KB)
        _set_state(ctx, S_NONE)
        return

    # Add text flow
    if st == S_ADD_TEXT:
        if _needs_profile(user.id):
            ctx.user_data["pending_food_text"] = text
            await _start_profile_flow(update.effective_chat, ctx)
            return
        await _show_confirm(update, ctx, text)
        return

    # Edit flow
    if st == S_EDIT:
        await _show_confirm(update, ctx, text)
        return

    await update.message.reply_text("Выбери действие кнопками ниже.", reply_markup=MAIN_KB)


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")

    if await _profile_step(update, ctx):
        return

    st = _get_state(ctx)
    if st != S_ADD_PHOTO:
        await update.message.reply_text("Фото принимаю только через: 🍽 Добавить еду → 📷 Фото", reply_markup=MAIN_KB)
        return

    photo = update.message.photo[-1]
    file = await ctx.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()

    recognized = analyze_food(bytes(data))
    await update.message.reply_text(f"Я вижу так:\n\n{recognized}\n")
    await _show_confirm(update, ctx, str(recognized))


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "")

    if await _profile_step(update, ctx):
        return

    st = _get_state(ctx)
    if st != S_ADD_VOICE:
        await update.message.reply_text("Голос принимаю только через: 🍽 Добавить еду → 🎤 Голос", reply_markup=MAIN_KB)
        return

    voice = update.message.voice
    file = await ctx.bot.get_file(voice.file_id)
    data = await file.download_as_bytearray()

    text = transcribe_voice(bytes(data))
    await update.message.reply_text(f"Распознал голос так:\n\n{text}\n")
    await _show_confirm(update, ctx, str(text))


async def profile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # force profile flow
    await _start_profile_flow(update.effective_chat, ctx)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is missing in .env")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile_cmd))

    app.add_handler(CallbackQueryHandler(on_callback))

    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()