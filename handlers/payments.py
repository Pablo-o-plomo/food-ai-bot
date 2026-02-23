import os
from datetime import datetime, timedelta
from telegram import LabeledPrice
from telegram.ext import ContextTypes
from users_db import ensure_user, update_user

PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
PRICE_RUB = 79000  # 790 ₽

async def buy_pro(update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id)

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="PRO доступ",
        description="Голос + фото + контроль питания. 30 дней.",
        payload="pro_30_days",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice("PRO 30 дней", PRICE_RUB)],
        start_parameter="pro"
    )

async def successful_payment(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    update_user(
        user_id,
        "subscription_end",
        (datetime.now() + timedelta(days=30)).isoformat()
    )
    update_user(user_id, "trial_used", True)

    await update.message.reply_text("🔥 PRO активирован на 30 дней.")