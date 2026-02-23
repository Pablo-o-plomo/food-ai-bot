from telegram.constants import ChatAction
from users_db import get_user, ensure_user
from services.access import has_pro
from services.ai import generate_voice_bytes

async def smart_reply(update, context, gpt_text: str):
    user_id = update.effective_user.id
    ensure_user(user_id)
    user = get_user(user_id)

    mode = user.get("mode", "text")

    # Если выбрали voice, но нет PRO/триала
    if mode == "voice" and not has_pro(user):
        await update.message.reply_text(
            "🎙 Голосовой режим доступен в PRO.\n"
            "Открой: Активировать PRO → Оплата или Промокод."
        )
        return

    if mode == "voice" and has_pro(user):
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.RECORD_VOICE)

        # голос коротко + потом текст полностью
        audio = generate_voice_bytes(gpt_text)

        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=audio
        )
        await update.message.reply_text(gpt_text)
        return

    # обычный текст
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    await update.message.reply_text(gpt_text)