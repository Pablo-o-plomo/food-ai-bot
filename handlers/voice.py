from telegram.constants import ChatAction
from users_db import get_user
from services.access import has_pro
from services.ai import generate_voice

async def smart_reply(update, context, gpt_text):
    user = get_user(update.effective_user.id)

    if user["mode"] == "voice" and has_pro(user):

        await context.bot.send_chat_action(
            update.effective_chat.id,
            ChatAction.RECORD_VOICE
        )

        audio = generate_voice(gpt_text, user["voice_style"])

        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=audio
        )

        await update.message.reply_text(gpt_text)

    else:
        await update.message.reply_text(gpt_text)