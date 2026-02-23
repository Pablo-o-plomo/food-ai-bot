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
from handlers.menu import main_menu
from handlers.voice import smart_reply
from services.ai import generate_text

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ===============================
# START
# ===============================

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    await update.message.reply_text(
        "Я — система контроля питания Павла Кузнецова.\n\n"
        "Шеф. Цифры. Питание без лишней воды.\n\n"
        "Выбери режим или просто напиши, что ты ел:",
        reply_markup=main_menu()
    )


# ===============================
# ПЕРЕКЛЮЧЕНИЕ РЕЖИМА
# ===============================

async def handle_mode(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if "Голосовой" in text:
        update_user(user_id, "mode", "voice")
        await update.message.reply_text("🎙 Голосовой режим активирован.")

    elif "Текстовый" in text:
        update_user(user_id, "mode", "text")
        await update.message.reply_text("💬 Текстовый режим активирован.")


# ===============================
# ОБРАБОТКА СООБЩЕНИЙ
# ===============================

async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    user_text = update.message.text

    # GPT ответ
    answer = generate_text(user_id, user_text)

    # Отправляем через smart_reply (учитывает голос / текст)
    await smart_reply(update, context, answer)


# ===============================
# MAIN
# ===============================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("Голосовой|Текстовый"),
            handle_mode
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()