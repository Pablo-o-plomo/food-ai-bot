import os
from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes

from users_db import activate_subscription, ensure_user, record_payment


def _provider_token() -> str | None:
    return os.getenv("PAYMENT_PROVIDER_TOKEN")


def _price_amount() -> int:
    raw = os.getenv("SUBSCRIPTION_PRICE", "79000")
    return int(raw)


def _currency() -> str:
    return os.getenv("CURRENCY", "RUB")


async def buy_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id, update.effective_user)
    provider_token = _provider_token()
    if not provider_token:
        await update.message.reply_text("Оплата временно недоступна: не настроен PAYMENT_PROVIDER_TOKEN.")
        return

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="PRO доступ",
        description="Больше фото, история за 30 дней и голосовой режим. 30 дней.",
        payload="pro_30_days",
        provider_token=provider_token,
        currency=_currency(),
        prices=[LabeledPrice("PRO 30 дней", _price_amount())],
        start_parameter="pro",
    )


async def pre_checkout_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "pro_30_days":
        await query.answer(ok=False, error_message="Некорректный платеж.")
        return
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id, update.effective_user)

    payment_id = record_payment(user_id, update.message.successful_payment)
    end = activate_subscription(user_id, days=30, payment_id=payment_id)

    await update.message.reply_text(f"🔥 PRO активирован на 30 дней. Доступ до {end.date()}.")
