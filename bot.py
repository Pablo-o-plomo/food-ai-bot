import os
from contextlib import asynccontextmanager
from decimal import Decimal

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from users_db import ensure_user, get_food_logs, get_profile, get_user, init_db, update_user
from services.access import has_pro
from services.ai import generate_text
from handlers.menu import main_menu, pro_menu
from handlers.voice import smart_reply
from handlers.promo import apply_promo_code
from handlers.payments import buy_pro, pre_checkout_query, successful_payment
from handlers.media import food_action_callback, handle_pending_food_text, handle_photo, handle_voice
from handlers.onboarding import (
    ACTIVITY,
    AGE,
    GOAL,
    HEIGHT,
    NAME,
    RESTRICTIONS,
    SEX,
    WEIGHT,
    cancel_onboarding,
    profile_command,
    set_activity,
    set_age,
    set_goal,
    set_height,
    set_name,
    set_restrictions,
    set_sex,
    set_weight,
    start_onboarding,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WAIT_PROMO = "WAIT_PROMO"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)
    profile = get_profile(user_id)

    if not profile or not profile.get("onboarding_completed"):
        await update.message.reply_text(
            "Привет. Я помогу считать еду по фото, голосу и тексту.\n"
            "Сначала заполним профиль для твоей дневной нормы."
        )
        return await start_onboarding(update, context)

    await update.message.reply_text(
        "Я — система контроля питания.\n"
        "Шеф. Цифры. Питание без лишней воды.\n\n"
        "Пришли фото еды, голос или напиши что ел.",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — запуск и onboarding\n"
        "/profile — профиль и дневная норма\n"
        "/today — итоги за сегодня\n"
        "/history — история: Free сегодня, PRO 30 дней\n"
        "/pay — оплата PRO\n"
        "/help — помощь\n\n"
        "После фото доступны кнопки: сохранить, исправить, изменить порцию, не сохранять, сегодня."
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user)
    await update.message.reply_text(today_text(update.effective_user.id))


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)
    user = get_user(user_id)
    days = 30 if has_pro(user) else 1
    title = "История за 30 дней" if days == 30 else "История Free: только сегодня"
    await update.message.reply_text(history_text(user_id, days=days, title=title))


async def pay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await buy_pro(update, context)


async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)
    text = update.message.text

    if "Голосовой" in text:
        update_user(user_id, "mode", "voice")
        await update.message.reply_text("🎙 Голосовой режим включён.", reply_markup=main_menu())

    elif "Текстовый" in text:
        update_user(user_id, "mode", "text")
        await update.message.reply_text("💬 Текстовый режим включён.", reply_markup=main_menu())


async def show_pro_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Активировать PRO:\nВыбери способ:", reply_markup=pro_menu())


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ок.", reply_markup=main_menu())


async def ask_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[WAIT_PROMO] = True
    await update.message.reply_text("Введи промокод одним сообщением (например KING30):")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)

    if await handle_pending_food_text(update, context):
        return

    if context.user_data.get(WAIT_PROMO):
        context.user_data[WAIT_PROMO] = False
        code = (update.message.text or "").strip()
        ok, msg = apply_promo_code(user_id, code)
        await update.message.reply_text(msg, reply_markup=main_menu())
        return

    user_text = update.message.text or ""
    answer = generate_text(user_id, user_text)
    await smart_reply(update, context, answer)


def today_text(user_id: int) -> str:
    profile = get_profile(user_id)
    logs = get_food_logs(user_id, days=1)
    return _logs_summary("📊 Сегодня", logs, profile)


def history_text(user_id: int, days: int, title: str) -> str:
    logs = get_food_logs(user_id, days=days)
    return _logs_summary(title, logs, get_profile(user_id), include_items=True)


def _logs_summary(title: str, logs: list[dict], profile: dict | None, include_items: bool = True) -> str:
    totals = {
        "calories": sum(_num(row.get("calories")) for row in logs),
        "protein": sum(_num(row.get("protein")) for row in logs),
        "fat": sum(_num(row.get("fat")) for row in logs),
        "carbs": sum(_num(row.get("carbs")) for row in logs),
    }
    lines = [title, ""]
    lines.append(f"Ккал: {totals['calories']:.0f}" + _target(profile, "daily_calories"))
    lines.append(f"Белки: {totals['protein']:.0f} г" + _target(profile, "daily_protein"))
    lines.append(f"Жиры: {totals['fat']:.0f} г" + _target(profile, "daily_fat"))
    lines.append(f"Углеводы: {totals['carbs']:.0f} г" + _target(profile, "daily_carbs"))

    if include_items:
        lines.append("")
        if not logs:
            lines.append("Записей пока нет.")
        else:
            for row in logs[:20]:
                lines.append(
                    f"• {row.get('log_date')}: {row.get('dish_name')} — "
                    f"{_num(row.get('calories')):.0f} ккал, Б{_num(row.get('protein')):.0f}/Ж{_num(row.get('fat')):.0f}/У{_num(row.get('carbs')):.0f}"
                )
    return "\n".join(lines)


def _num(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _target(profile: dict | None, key: str) -> str:
    if not profile or profile.get(key) is None:
        return ""
    return f" / {float(profile[key]):.0f}"


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("profile", profile_command)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_age)],
            SEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sex)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_weight)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_goal)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_activity)],
            RESTRICTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_restrictions)],
        },
        fallbacks=[CommandHandler("cancel", cancel_onboarding)],
    )

    app.add_handler(onboarding)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("pay", pay_command))

    app.add_handler(CallbackQueryHandler(food_action_callback, pattern="^food:"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎙 Голосовой режим$|^💬 Текстовый режим$"), handle_mode))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔥 Активировать PRO$"), show_pro_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⬅️ Назад$"), back_to_main))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💳 Оплатить PRO$"), buy_pro))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎟 Ввести промокод$"), ask_promo))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_query))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def run_polling(application: Application) -> None:
    print("Bot started in polling mode...")
    application.run_polling()


def create_fastapi_app(application: Application):
    from fastapi import FastAPI, Request
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook")
    public_url = os.getenv("PUBLIC_URL")
    if not public_url:
        raise RuntimeError("PUBLIC_URL is required in webhook mode")
    webhook_url = public_url.rstrip("/") + webhook_path

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await application.initialize()
        await application.bot.set_webhook(webhook_url)
        await application.start()
        yield
        await application.stop()
        await application.bot.delete_webhook()
        await application.shutdown()

    api = FastAPI(lifespan=lifespan)

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    @api.post(webhook_path)
    async def telegram_webhook(request: Request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return {"ok": True}

    return api


def main():
    init_db()
    application = build_application()
    mode = os.getenv("BOT_MODE", "polling").lower()

    if mode == "webhook":
        import uvicorn

        port = int(os.getenv("PORT", "8080"))
        uvicorn.run(create_fastapi_app(application), host="0.0.0.0", port=port)
        return

    run_polling(application)


if __name__ == "__main__":
    main()
