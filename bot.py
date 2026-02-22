import os
import re
from datetime import date
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
from dotenv import load_dotenv

from vision import analyze_food
from food_text_ai import analyze_text_food
from voice_ai import transcribe_voice
from coach_ai import coach_chat
from users_db import (
    ensure_user,
    get_ui,
    set_ui,
    clear_ui_await,
    add_food,
    get_day,
    undo_last,
    reset_day,
    set_goal,
    get_goal,
    set_profile_field,
    get_profile,
    is_profile_complete,
)
from targets import calculate_targets

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")


# =========================
# UI: Главный экран (ReplyKeyboard)
# =========================
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🍽 Добавить еду"), KeyboardButton("📊 Сегодня")],
        [KeyboardButton("💬 Совет"), KeyboardButton("⚙️ Профиль")],
    ],
    resize_keyboard=True,
)


# =========================
# Inline меню (внутри разделов)
# =========================
def ik_add_food():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📸 Фото", callback_data="add:photo")],
            [InlineKeyboardButton("🎤 Голос", callback_data="add:voice")],
            [InlineKeyboardButton("✍️ Текст", callback_data="add:text")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
        ]
    )


def ik_today():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("↩️ Отменить последнее", callback_data="today:undo")],
            [InlineKeyboardButton("🧹 Сбросить день", callback_data="today:reset")],
            [InlineKeyboardButton("📜 История (5)", callback_data="today:history")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
        ]
    )


def ik_coach():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("😋 Хочу сладкое", callback_data="coach:quick:sweet")],
            [InlineKeyboardButton("🍝 Хочу сытное", callback_data="coach:quick:full")],
            [InlineKeyboardButton("🥗 Хочу лёгкое", callback_data="coach:quick:light")],
            [InlineKeyboardButton("💪 Добрать белок", callback_data="coach:quick:protein")],
            [InlineKeyboardButton("🌙 Что на ужин", callback_data="coach:quick:dinner")],
            [InlineKeyboardButton("❓ Задать вопрос", callback_data="coach:ask")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
        ]
    )


def ik_profile():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 Цель", callback_data="prof:goal")],
            [InlineKeyboardButton("👤 Параметры", callback_data="prof:params")],
            [InlineKeyboardButton("📈 Моя норма", callback_data="prof:targets")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="nav:home")],
        ]
    )


def ik_goal():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎯 Похудеть", callback_data="goal:lose")],
            [InlineKeyboardButton("⚖️ Поддерживать", callback_data="goal:maintain")],
            [InlineKeyboardButton("💪 Набрать массу", callback_data="goal:gain")],
            [InlineKeyboardButton("❤️ Здоровье", callback_data="goal:health")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="prof:back")],
        ]
    )


def ik_back_to_profile():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Назад", callback_data="prof:back")]]
    )


# =========================
# Helpers
# =========================
def extract_nutrition(text: str):
    """
    Ожидаем 5 строк:
    Название: ...
    Калории: число
    Белки: число
    Жиры: число
    Углеводы: число
    """
    try:
        calories = re.search(r"Калории:\s*([\d\.,]+)", text)
        protein = re.search(r"Белки:\s*([\d\.,]+)", text)
        fat = re.search(r"Жиры:\s*([\d\.,]+)", text)
        carbs = re.search(r"Углеводы:\s*([\d\.,]+)", text)

        def f(m):
            return float(m.group(1).replace(",", "."))

        return f(calories), f(protein), f(fat), f(carbs)
    except:
        return None


def short_day(day: dict) -> str:
    return f"{round(day['calories'])} ккал | Б {round(day['protein'])}г Ж {round(day['fat'])}г У {round(day['carbs'])}г"


def goal_name(g):
    return {"lose": "Похудеть", "maintain": "Поддерживать", "gain": "Набрать массу", "health": "Здоровье"}.get(g, "—")


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбирай действие 👇",
        reply_markup=MAIN_KB
    )


async def show_targets_text(user_id: int) -> str:
    g = get_goal(user_id)
    prof = get_profile(user_id)
    if not g:
        return "Цель не выбрана."
    if not is_profile_complete(user_id):
        return "Профиль не заполнен."
    t = calculate_targets(prof, g)
    return (
        f"📈 Норма на день\n"
        f"Цель: {goal_name(g)}\n"
        f"Калории: {round(t['calories'])} ккал\n"
        f"Белки: {round(t['protein_g'])} г\n"
        f"Жиры: {round(t['fat_g'])} г\n"
        f"Углеводы: {round(t['carbs_g'])} г"
    )


async def add_food_flow(update: Update, nutrition_text: str, source_label: str = "Еда"):
    user_id = update.message.from_user.id
    n = extract_nutrition(nutrition_text)
    if not n:
        await update.message.reply_text("Не смог посчитать 😔 Попробуй ещё раз.", reply_markup=MAIN_KB)
        return

    cal, pr, fat, carb = n
    add_food(user_id, cal, pr, fat, carb)

    day = get_day(user_id)
    msg = f"✅ Записал: +{round(cal)} ккал\nСегодня: {short_day(day)}"

    # если есть цель+профиль — покажем остаток
    if get_goal(user_id) and is_profile_complete(user_id):
        t = calculate_targets(get_profile(user_id), get_goal(user_id))
        left = max(0, round(t["calories"] - day["calories"]))
        msg += f"\nОсталось: ~{left} ккал"

    await update.message.reply_text(msg, reply_markup=MAIN_KB)
    clear_ui_await(user_id)


# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.message.from_user.id)
    await update.message.reply_text(
        "Привет! 👋\n"
        "Я — бот питания 🍽\n\n"
        "Главное правило:\n"
        "🍽 «Добавить еду» — записывает\n"
        "💬 «Совет» — НЕ записывает, только помогает 🙂",
        reply_markup=MAIN_KB
    )


# =========================
# Reply buttons (главные 4)
# =========================
async def on_main_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    ensure_user(user_id)

    text = (update.message.text or "").strip()
    ui = get_ui(user_id)

    # если пользователь в ожидании ввода (await) — обработаем ниже
    # но сначала — навигация главными кнопками
    if text == "🍽 Добавить еду":
        set_ui(user_id, section="add", await_kind=None, wizard=None)
        await update.message.reply_text("Как добавим еду? 👇", reply_markup=ik_add_food())
        return

    if text == "📊 Сегодня":
        set_ui(user_id, section="today", await_kind=None, wizard=None)
        day = get_day(user_id)
        base = f"📊 Сегодня\n{short_day(day)}"
        if get_goal(user_id) and is_profile_complete(user_id):
            t = calculate_targets(get_profile(user_id), get_goal(user_id))
            left = max(0, round(t["calories"] - day["calories"]))
            base += f"\nНорма: {round(t['calories'])} ккал\nОсталось: ~{left} ккал"
        else:
            base += "\n\n⚙️ Заполни цель и профиль — покажу норму."
        await update.message.reply_text(base, reply_markup=ik_today())
        return

    if text == "💬 Совет":
        set_ui(user_id, section="coach", await_kind=None, wizard=None)
        await update.message.reply_text("Ок 🙂 Чем помочь?", reply_markup=ik_coach())
        return

    if text == "⚙️ Профиль":
        set_ui(user_id, section="profile", await_kind=None, wizard=None)
        await update.message.reply_text("Профиль 👤", reply_markup=ik_profile())
        return

    # если нет главной кнопки — значит это ввод по state-machine
    await handle_state_input(update, context)


# =========================
# Inline callbacks
# =========================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    ensure_user(user_id)

    data = query.data or ""
    ui = get_ui(user_id)

    # навигация
    if data == "nav:home":
        set_ui(user_id, section="home", await_kind=None, wizard=None)
        await query.message.reply_text("Ок 👇", reply_markup=MAIN_KB)
        return

    # ADD FOOD
    if data == "add:photo":
        set_ui(user_id, section="add", await_kind="photo", wizard=None)
        await query.message.reply_text("📸 Пришли фото еды 🙂", reply_markup=MAIN_KB)
        return

    if data == "add:voice":
        set_ui(user_id, section="add", await_kind="voice", wizard=None)
        await query.message.reply_text("🎤 Запиши голосовое: что съел 🙂", reply_markup=MAIN_KB)
        return

    if data == "add:text":
        set_ui(user_id, section="add", await_kind="text", wizard=None)
        await query.message.reply_text("✍️ Напиши, что съел. Например: «2 яйца и хлеб»", reply_markup=MAIN_KB)
        return

    # TODAY actions
    if data == "today:undo":
        day = undo_last(user_id)
        if not day:
            await query.message.reply_text("Пока нечего отменять 🙂", reply_markup=MAIN_KB)
        else:
            await query.message.reply_text(f"↩️ Откатил последнее.\nТеперь: {short_day(day)}", reply_markup=MAIN_KB)
        return

    if data == "today:reset":
        reset_day(user_id)
        await query.message.reply_text("🧹 День обнулён. Начинаем заново 🙂", reply_markup=MAIN_KB)
        return

    if data == "today:history":
        day = get_day(user_id)
        hist = day.get("history", [])[-5:]
        if not hist:
            await query.message.reply_text("История пустая 🙂", reply_markup=MAIN_KB)
            return
        lines = []
        for i, h in enumerate(hist, 1):
            lines.append(f"{i}) {round(h.get('calories', 0))} ккал")
        await query.message.reply_text("📜 Последние 5 записей:\n" + "\n".join(lines), reply_markup=MAIN_KB)
        return

    # COACH
    if data == "coach:ask":
        set_ui(user_id, section="coach", await_kind="coach_question", wizard=None)
        await query.message.reply_text("Задай вопрос 🙂 (я отвечу, но НЕ записываю в дневник)", reply_markup=MAIN_KB)
        return

    if data.startswith("coach:quick:"):
        kind = data.split(":")[-1]
        quick_map = {
            "sweet": "Хочу сладкое. Дай 5 вариантов перекуса лучше шоколадки.",
            "full": "Хочу сытное. Дай 5 вариантов, чтобы было вкусно и норм по калориям.",
            "light": "Хочу лёгкое. Дай 5 вариантов еды/перекуса.",
            "protein": "Нужно добрать белок. Дай 5 вариантов.",
            "dinner": "Что лучше на ужин сегодня? Дай 5 вариантов.",
        }
        q = quick_map.get(kind, "Дай идеи еды.")
        targets = None
        day = None
        if get_goal(user_id) and is_profile_complete(user_id):
            targets = calculate_targets(get_profile(user_id), get_goal(user_id))
            day = get_day(user_id)
        answer = coach_chat(q, targets=targets, day=day, goal=get_goal(user_id))
        await query.message.reply_text(answer, reply_markup=MAIN_KB)
        return

    # PROFILE
    if data == "prof:back":
        set_ui(user_id, section="profile", await_kind=None, wizard=None)
        await query.message.reply_text("Профиль 👤", reply_markup=ik_profile())
        return

    if data == "prof:goal":
        await query.message.reply_text("🎯 Выбери цель:", reply_markup=ik_goal())
        return

    if data.startswith("goal:"):
        g = data.split(":")[1]
        set_goal(user_id, g)
        await query.message.reply_text(f"Цель выбрана: {goal_name(g)} ✅", reply_markup=ik_back_to_profile())
        return

    if data == "prof:params":
        # запустим wizard параметров
        set_ui(user_id, section="profile", await_kind=None, wizard="age")
        await query.message.reply_text("👤 Параметры\nСколько тебе лет? (числом)", reply_markup=MAIN_KB)
        return

    if data == "prof:targets":
        txt = await show_targets_text(user_id)
        await query.message.reply_text(txt, reply_markup=ik_back_to_profile())
        return


# =========================
# State-machine inputs (text)
# =========================
async def handle_state_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    ui = get_ui(user_id)
    text = (update.message.text or "").strip()

    # 1) Wizard профиля
    if ui.get("wizard") in ("age", "sex", "height", "weight", "activity"):
        await handle_profile_wizard(update, context)
        return

    # 2) Await coach question
    if ui.get("await") == "coach_question":
        targets = None
        day = None
        if get_goal(user_id) and is_profile_complete(user_id):
            targets = calculate_targets(get_profile(user_id), get_goal(user_id))
            day = get_day(user_id)
        answer = coach_chat(text, targets=targets, day=day, goal=get_goal(user_id))
        await update.message.reply_text(answer, reply_markup=MAIN_KB)
        clear_ui_await(user_id)
        return

    # 3) Await add food by text
    if ui.get("await") == "text":
        await update.message.reply_text("Считаю… 🧮", reply_markup=MAIN_KB)
        nutrition_text = analyze_text_food(text)
        await add_food_flow(update, nutrition_text, source_label="Текст")
        return

    # Если пользователь написал что-то в “пустом” состоянии — мягко направим
    await update.message.reply_text(
        "Я понял 🙂\n"
        "Чтобы записать еду — нажми «🍽 Добавить еду»\n"
        "Чтобы спросить — «💬 Совет»",
        reply_markup=MAIN_KB
    )


async def handle_profile_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    ui = get_ui(user_id)
    step = ui.get("wizard")
    text = (update.message.text or "").strip()

    def is_num(x):
        try:
            float(x.replace(",", "."))
            return True
        except:
            return False

    if step == "age":
        if not is_num(text):
            await update.message.reply_text("Возраст числом 🙂 Например: 32", reply_markup=MAIN_KB)
            return
        set_profile_field(user_id, "age", int(float(text.replace(",", "."))))
        set_ui(user_id, wizard="sex")
        await update.message.reply_text("Пол? Напиши: М или Ж", reply_markup=MAIN_KB)
        return

    if step == "sex":
        t = text.upper()
        if t not in ("М", "Ж"):
            await update.message.reply_text("Только М или Ж 🙂", reply_markup=MAIN_KB)
            return
        set_profile_field(user_id, "sex", "male" if t == "М" else "female")
        set_ui(user_id, wizard="height")
        await update.message.reply_text("Рост (см)?", reply_markup=MAIN_KB)
        return

    if step == "height":
        if not is_num(text):
            await update.message.reply_text("Рост числом 🙂 Например: 178", reply_markup=MAIN_KB)
            return
        set_profile_field(user_id, "height_cm", int(float(text.replace(",", "."))))
        set_ui(user_id, wizard="weight")
        await update.message.reply_text("Вес (кг)?", reply_markup=MAIN_KB)
        return

    if step == "weight":
        if not is_num(text):
            await update.message.reply_text("Вес числом 🙂 Например: 84", reply_markup=MAIN_KB)
            return
        set_profile_field(user_id, "weight_kg", float(text.replace(",", ".")))
        set_ui(user_id, wizard="activity")
        await update.message.reply_text(
            "Активность? Напиши цифру:\n"
            "1 — низкая (офис)\n"
            "2 — средняя (2-3 тренировки)\n"
            "3 — высокая (спорт/физработа)",
            reply_markup=MAIN_KB
        )
        return

    if step == "activity":
        if text not in ("1", "2", "3"):
            await update.message.reply_text("Выбери 1 / 2 / 3 🙂", reply_markup=MAIN_KB)
            return
        factor = {"1": 1.2, "2": 1.45, "3": 1.7}[text]
        set_profile_field(user_id, "activity_factor", factor)
        set_ui(user_id, wizard=None)
        await update.message.reply_text("Готово ✅ Профиль сохранён.", reply_markup=MAIN_KB)
        # если цель уже есть — покажем норму
        if get_goal(user_id):
            txt = await show_targets_text(user_id)
            await update.message.reply_text(txt, reply_markup=MAIN_KB)
        return


# =========================
# Photo handler
# =========================
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    ensure_user(user_id)

    ui = get_ui(user_id)

    # Фото трактуем как "еда" (логично всегда)
    photo_file = await update.message.photo[-1].get_file()
    file_path = "food.jpg"
    await photo_file.download_to_drive(file_path)

    await update.message.reply_text("📸 Секунду… распознаю еду 👀", reply_markup=MAIN_KB)

    try:
        nutrition_text = analyze_food(file_path)
        await add_food_flow(update, nutrition_text, source_label="Фото")
    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог разобрать фото 😔", reply_markup=MAIN_KB)


# =========================
# Voice handler
# =========================
async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    ensure_user(user_id)

    ui = get_ui(user_id)

    voice = await update.message.voice.get_file()
    file_path = "voice.ogg"
    await voice.download_to_drive(file_path)

    await update.message.reply_text("🎧 Слушаю…", reply_markup=MAIN_KB)

    try:
        text = transcribe_voice(file_path)

        # если ожидали вопрос коучу — отвечаем, не записываем
        if ui.get("await") == "coach_question":
            targets = None
            day = None
            if get_goal(user_id) and is_profile_complete(user_id):
                targets = calculate_targets(get_profile(user_id), get_goal(user_id))
                day = get_day(user_id)
            answer = coach_chat(text, targets=targets, day=day, goal=get_goal(user_id))
            await update.message.reply_text(answer, reply_markup=MAIN_KB)
            clear_ui_await(user_id)
            return

        # если ожидали голос как "еда" — считаем еду
        nutrition_text = analyze_text_food(text)
        await add_food_flow(update, nutrition_text, source_label="Голос")

    except Exception as e:
        print(e)
        await update.message.reply_text("Не смог распознать голос 😔", reply_markup=MAIN_KB)


# =========================
# Run
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # inline callbacks
    app.add_handler(CallbackQueryHandler(on_callback))

    # content handlers
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))

    # text (главные кнопки + state inputs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_main_text))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()