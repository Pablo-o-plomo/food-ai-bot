from telegram.constants import ChatAction
from users_db import ensure_user
from services.ai import generate_text
from services.stt import transcribe_ogg
from services.vision import analyze_food_photo
from handlers.voice import smart_reply


async def handle_voice(update, context):
    user_id = update.effective_user.id
    ensure_user(user_id)

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


async def handle_photo(update, context):
    user_id = update.effective_user.id
    ensure_user(user_id)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    if not update.message.photo:
        await update.message.reply_text("Пришли фото как изображение (не файлом).")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    img_bytes = await file.download_as_bytearray()

    vision = analyze_food_photo(bytes(img_bytes))

    prompt = (
        "Пользователь прислал фото еды.\n"
        f"Распознавание:\n{vision}\n\n"
        "Ответь пользователю коротко, по делу. Можно задать 1 уточняющий вопрос."
    )

    answer = generate_text(user_id, prompt)
    await smart_reply(update, context, answer)