from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from targets import calculate_targets
from users_db import ensure_user, get_profile, save_profile

NAME, AGE, SEX, HEIGHT, WEIGHT, GOAL, ACTIVITY, RESTRICTIONS = range(8)

SEX_MAP = {
    "мужской": "male",
    "женский": "female",
    "м": "male",
    "ж": "female",
    "male": "male",
    "female": "female",
}

GOAL_MAP = {
    "похудение": "lose",
    "поддержание": "maintain",
    "набор": "gain",
    "здоровье": "health",
}

ACTIVITY_MAP = {
    "низкая": 1.2,
    "легкая": 1.375,
    "средняя": 1.55,
    "высокая": 1.725,
}


def _keyboard(items: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[item] for item in items], resize_keyboard=True, one_time_keyboard=True)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user)
    context.user_data["onboarding"] = {}
    await update.message.reply_text(
        "Соберём профиль, чтобы считать дневную норму.\n\nКак тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user)
    profile = get_profile(update.effective_user.id)
    if not profile or not profile.get("onboarding_completed"):
        await update.message.reply_text("Профиль ещё не заполнен. Запускаю onboarding.")
        return await start_onboarding(update, context)

    await update.message.reply_text(_format_profile(profile))
    return ConversationHandler.END


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if len(name) < 2:
        await update.message.reply_text("Напиши имя текстом, минимум 2 символа.")
        return NAME
    context.user_data["onboarding"]["name"] = name
    await update.message.reply_text("Возраст? Напиши число лет.")
    return AGE


async def set_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int((update.message.text or "").strip())
    except ValueError:
        age = 0
    if age < 10 or age > 100:
        await update.message.reply_text("Возраст должен быть числом от 10 до 100.")
        return AGE
    context.user_data["onboarding"]["age"] = age
    await update.message.reply_text("Пол?", reply_markup=_keyboard(["Мужской", "Женский"]))
    return SEX


async def set_sex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip().lower()
    sex = SEX_MAP.get(raw)
    if not sex:
        await update.message.reply_text("Выбери: Мужской или Женский.", reply_markup=_keyboard(["Мужской", "Женский"]))
        return SEX
    context.user_data["onboarding"]["sex"] = sex
    await update.message.reply_text("Рост в сантиметрах? Например: 178", reply_markup=ReplyKeyboardRemove())
    return HEIGHT


async def set_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float((update.message.text or "").replace(",", "."))
    except ValueError:
        height = 0
    if height < 100 or height > 250:
        await update.message.reply_text("Рост должен быть числом от 100 до 250 см.")
        return HEIGHT
    context.user_data["onboarding"]["height_cm"] = height
    await update.message.reply_text("Вес в кг? Например: 82.5")
    return WEIGHT


async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float((update.message.text or "").replace(",", "."))
    except ValueError:
        weight = 0
    if weight < 30 or weight > 300:
        await update.message.reply_text("Вес должен быть числом от 30 до 300 кг.")
        return WEIGHT
    context.user_data["onboarding"]["weight_kg"] = weight
    await update.message.reply_text(
        "Цель?",
        reply_markup=_keyboard(["Похудение", "Поддержание", "Набор", "Здоровье"]),
    )
    return GOAL


async def set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip().lower()
    goal = GOAL_MAP.get(raw)
    if not goal:
        await update.message.reply_text("Выбери цель кнопкой.", reply_markup=_keyboard(["Похудение", "Поддержание", "Набор", "Здоровье"]))
        return GOAL
    context.user_data["onboarding"]["goal"] = goal
    await update.message.reply_text(
        "Активность?",
        reply_markup=_keyboard(["Низкая", "Легкая", "Средняя", "Высокая"]),
    )
    return ACTIVITY


async def set_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip().lower().replace("ё", "е")
    activity = ACTIVITY_MAP.get(raw)
    if not activity:
        await update.message.reply_text("Выбери активность кнопкой.", reply_markup=_keyboard(["Низкая", "Легкая", "Средняя", "Высокая"]))
        return ACTIVITY
    context.user_data["onboarding"]["activity_factor"] = activity
    await update.message.reply_text(
        "Ограничения по еде? Например: без свинины, lactose-free, аллергия на орехи. Если нет — напиши Нет.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RESTRICTIONS


async def set_restrictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    restrictions = (update.message.text or "").strip()
    data = context.user_data.get("onboarding", {})
    data["food_restrictions"] = restrictions
    targets = calculate_targets(data, data["goal"])
    profile = {
        **data,
        "daily_calories": round(targets["calories"], 0),
        "daily_protein": round(targets["protein_g"], 0),
        "daily_fat": round(targets["fat_g"], 0),
        "daily_carbs": round(targets["carbs_g"], 0),
    }
    save_profile(update.effective_user.id, profile)
    context.user_data.pop("onboarding", None)
    await update.message.reply_text(
        "Профиль готов.\n\n" + _format_profile(profile) + "\n\nТеперь пришли фото еды или напиши, что ел.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("onboarding", None)
    await update.message.reply_text("Ок, остановил заполнение профиля.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def _format_profile(profile: dict) -> str:
    goals = {"lose": "похудение", "maintain": "поддержание", "gain": "набор", "health": "здоровье"}
    sexes = {"male": "мужской", "female": "женский"}
    return (
        f"👤 Профиль: {profile.get('name')}\n"
        f"Возраст: {profile.get('age')}\n"
        f"Пол: {sexes.get(profile.get('sex'), profile.get('sex'))}\n"
        f"Рост/вес: {profile.get('height_cm')} см / {profile.get('weight_kg')} кг\n"
        f"Цель: {goals.get(profile.get('goal'), profile.get('goal'))}\n"
        f"Ограничения: {profile.get('food_restrictions') or 'нет'}\n\n"
        f"🎯 Норма на день:\n"
        f"Ккал: {profile.get('daily_calories')}\n"
        f"Белки: {profile.get('daily_protein')} г\n"
        f"Жиры: {profile.get('daily_fat')} г\n"
        f"Углеводы: {profile.get('daily_carbs')} г"
    )
