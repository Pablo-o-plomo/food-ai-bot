import os
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from users_db import ensure_user, update_user, get_user
from handlers.menu import main_menu, pro_menu
from handlers.voice import smart_reply
from services.ai import generate_text
from handlers.promo import apply_promo_code
from handlers.payments import buy_pro, successful_payment
from handlers.media import handle_voice, handle_photo

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

WAIT_PROMO = "WAIT_PROMO"


async def start(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    await update.message.reply_text(
        "Я — система контроля питания.\n"
        "Шеф. Цифры. Питание без лишней воды.\n\n"
        "Напиши что ел или выбери режим.",
        reply_markup=main_menu()
    )


async def handle_mode(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)
    text = update.message.text

    if "Голосовой" in text:
        update_user(user_id, "mode", "voice")
        await update.message.reply_text("🎙 Голосовой режим включён.", reply_markup=main_menu())

    elif "Текстовый" in text:
        update_user(user_id, "mode", "text")
        await update.message.reply_text("💬 Текстовый режим включён.", reply_markup=main_menu())


async def show_pro_menu(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Активировать PRO:\nВыбери способ:",
        reply_markup=pro_menu()
    )


async def back_to_main(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ок.", reply_markup=main_menu())


async def ask_promo(update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[WAIT_PROMO] = True
    await update.message.reply_text("Введи промокод одним сообщением (например KING30):")


async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    # ожидаем промокод
    if context.user_data.get(WAIT_PROMO):
        context.user_data[WAIT_PROMO] = False
        code = (update.message.text or "").strip()
        ok, msg = apply_promo_code(user_id, code)
        await update.message.reply_text(msg, reply_markup=main_menu())
        return

    user_text = update.message.text or ""
    answer = generate_text(user_id, user_text)
    await smart_reply(update, context, answer)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # start
    app.add_handler(CommandHandler("start", start))

    # media first
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # menus
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎙 Голосовой режим$|^💬 Текстовый режим$"), handle_mode))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔥 Активировать PRO$"), show_pro_menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^⬅️ Назад$"), back_to_main))

    # pro actions
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💳 Оплатить PRO$"), buy_pro))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🎟 Ввести промокод$"), ask_promo))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()