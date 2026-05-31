import re
from decimal import Decimal
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from users_db import add_food_log, consume_photo_quota, ensure_user, get_food_logs, get_profile, get_user
from services.access import has_pro
from services.ai import generate_text
from services.stt import transcribe_ogg
from services.vision import analyze_food_photo
from handlers.voice import smart_reply

PENDING_FOOD_KEY = "pending_food"
PHOTO_FREE_LIMIT = 3


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    voice = update.message.voice
    if not voice:
        await update.message.reply_text("Не вижу голосовое. Пришли ещё раз.")
        return

    file = await context.bot.get_file(voice.file_id)
    ogg_bytes = await file.download_as_bytearray()

    text = transcribe_ogg(bytes(ogg_bytes))
    if not text:
        await update.message.reply_text("Не разобрал голос. Скажи короче и чётче.")
        return

    answer = generate_text(user_id, text)
    await smart_reply(update, context, answer)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)
    user = get_user(user_id)

    if not has_pro(user):
        allowed, used = consume_photo_quota(user_id, PHOTO_FREE_LIMIT)
        if not allowed:
            await update.message.reply_text(
                "Лимит Free: 3 фото в день.\n"
                "Для большего количества и истории за 30 дней открой /pay."
            )
            return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    if not update.message.photo:
        await update.message.reply_text("Пришли фото как изображение (не файлом).")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()

    vision = analyze_food_photo(bytes(img_bytes))
    parsed = parse_food_ai_response(vision)
    context.user_data[PENDING_FOOD_KEY] = {**parsed, "raw_ai_response": vision, "source": "photo"}

    await update.message.reply_text(
        _format_food_result(parsed, vision),
        reply_markup=food_action_keyboard(),
    )


async def food_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    pending = context.user_data.get(PENDING_FOOD_KEY)

    if not pending and action != "food:today":
        await query.edit_message_text("Нет блюда для сохранения. Пришли новое фото еды.")
        return

    if action == "food:save":
        log_id = add_food_log(
            update.effective_user.id,
            pending["dish_name"],
            pending["calories"],
            pending["protein"],
            pending["fat"],
            pending["carbs"],
            pending["raw_ai_response"],
            pending["source"],
        )
        context.user_data.pop(PENDING_FOOD_KEY, None)
        await query.edit_message_text(f"✅ Сохранил в дневник. Запись #{log_id}.")
        return

    if action == "food:discard":
        context.user_data.pop(PENDING_FOOD_KEY, None)
        await query.edit_message_text("❌ Не сохраняю.")
        return

    if action == "food:today":
        await query.message.reply_text(_today_text(update.effective_user.id))
        return

    if action == "food:edit":
        context.user_data["awaiting_food_edit"] = True
        await query.message.reply_text(
            "Напиши исправление одной строкой: название; ккал; белки; жиры; углеводы\n"
            "Пример: Омлет с сыром; 420; 28; 30; 6"
        )
        return

    if action == "food:portion":
        context.user_data["awaiting_food_portion"] = True
        await query.message.reply_text(
            "Напиши коэффициент порции. Например: 0.5 — половина, 1.5 — на 50% больше, 2 — в два раза."
        )
        return


async def handle_pending_food_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    pending = context.user_data.get(PENDING_FOOD_KEY)
    if not pending:
        return False

    if context.user_data.pop("awaiting_food_edit", False):
        parsed = parse_manual_food_line(update.message.text or "")
        if not parsed:
            context.user_data["awaiting_food_edit"] = True
            await update.message.reply_text("Не понял. Формат: название; ккал; белки; жиры; углеводы")
            return True
        context.user_data[PENDING_FOOD_KEY] = {**pending, **parsed}
        await update.message.reply_text(
            _format_food_result(context.user_data[PENDING_FOOD_KEY], context.user_data[PENDING_FOOD_KEY]["raw_ai_response"]),
            reply_markup=food_action_keyboard(),
        )
        return True

    if context.user_data.pop("awaiting_food_portion", False):
        try:
            factor = float((update.message.text or "").replace(",", "."))
        except ValueError:
            factor = 0
        if factor <= 0 or factor > 10:
            context.user_data["awaiting_food_portion"] = True
            await update.message.reply_text("Коэффициент должен быть числом больше 0 и не больше 10.")
            return True
        for key in ("calories", "protein", "fat", "carbs"):
            pending[key] = round(float(pending.get(key) or 0) * factor, 1)
        pending["raw_ai_response"] += f"\n\nПорция изменена пользователем: x{factor}."
        context.user_data[PENDING_FOOD_KEY] = pending
        await update.message.reply_text(_format_food_result(pending, pending["raw_ai_response"]), reply_markup=food_action_keyboard())
        return True

    return False


def food_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Сохранить", callback_data="food:save"), InlineKeyboardButton("❌ Не сохранять", callback_data="food:discard")],
            [InlineKeyboardButton("✏️ Исправить", callback_data="food:edit"), InlineKeyboardButton("⚖️ Изменить порцию", callback_data="food:portion")],
            [InlineKeyboardButton("📊 Сегодня", callback_data="food:today")],
        ]
    )


def parse_food_ai_response(text: str) -> dict[str, Any]:
    lower = text.lower()
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    dish_name = lines[0]
    for prefix in ("что на фото:", "название:", "блюдо:", "1)"):
        if dish_name.lower().startswith(prefix):
            dish_name = dish_name[len(prefix):].strip()

    calories = _find_number(lower, [r"(\d+(?:[\.,]\d+)?)\s*(?:ккал|калор)", r"калории\D+(\d+(?:[\.,]\d+)?)"])
    protein = _find_number(lower, [r"белк\w*\D+(\d+(?:[\.,]\d+)?)", r"(\d+(?:[\.,]\d+)?)\s*г?\s*бел"])
    fat = _find_number(lower, [r"жир\w*\D+(\d+(?:[\.,]\d+)?)", r"(\d+(?:[\.,]\d+)?)\s*г?\s*жир"])
    carbs = _find_number(lower, [r"углевод\w*\D+(\d+(?:[\.,]\d+)?)", r"(\d+(?:[\.,]\d+)?)\s*г?\s*угл"])

    return {
        "dish_name": dish_name[:200] or "Еда с фото",
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbs": carbs,
    }


def parse_manual_food_line(text: str) -> dict[str, Any] | None:
    parts = [p.strip() for p in text.split(";")]
    if len(parts) != 5 or not parts[0]:
        return None
    try:
        return {
            "dish_name": parts[0][:200],
            "calories": float(parts[1].replace(",", ".")),
            "protein": float(parts[2].replace(",", ".")),
            "fat": float(parts[3].replace(",", ".")),
            "carbs": float(parts[4].replace(",", ".")),
        }
    except ValueError:
        return None


def _find_number(text: str, patterns: list[str]) -> float:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return 0.0


def _format_food_result(parsed: dict, raw: str) -> str:
    return (
        "🍽 Распознал еду:\n"
        f"{raw}\n\n"
        "Оценка для дневника:\n"
        f"Блюдо: {parsed.get('dish_name')}\n"
        f"Ккал: {parsed.get('calories', 0)}\n"
        f"Белки: {parsed.get('protein', 0)} г\n"
        f"Жиры: {parsed.get('fat', 0)} г\n"
        f"Углеводы: {parsed.get('carbs', 0)} г"
    )


def _today_text(user_id: int) -> str:
    profile = get_profile(user_id)
    logs = get_food_logs(user_id, days=1)
    totals = {
        "calories": sum(_num(row.get("calories")) for row in logs),
        "protein": sum(_num(row.get("protein")) for row in logs),
        "fat": sum(_num(row.get("fat")) for row in logs),
        "carbs": sum(_num(row.get("carbs")) for row in logs),
    }
    return (
        "📊 Сегодня\n\n"
        f"Ккал: {totals['calories']:.0f}{_target(profile, 'daily_calories')}\n"
        f"Белки: {totals['protein']:.0f} г{_target(profile, 'daily_protein')}\n"
        f"Жиры: {totals['fat']:.0f} г{_target(profile, 'daily_fat')}\n"
        f"Углеводы: {totals['carbs']:.0f} г{_target(profile, 'daily_carbs')}"
    )


def _num(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _target(profile: dict | None, key: str) -> str:
    if not profile or profile.get(key) is None:
        return ""
    return f" / {float(profile[key]):.0f}"
