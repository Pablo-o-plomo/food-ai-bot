# food-ai-bot

Telegram bot for food recognition, nutrition logging, onboarding, subscriptions and Railway webhook deployment.

## Required environment

- `BOT_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL`

## Payments

- `PAYMENT_PROVIDER_TOKEN`
- `SUBSCRIPTION_PRICE` — amount in the smallest currency unit, e.g. `79000` for 790 RUB
- `CURRENCY` — e.g. `RUB`

## Runtime mode

Polling:

```bash
BOT_MODE=polling python bot.py
```

Webhook for Railway:

```bash
BOT_MODE=webhook PUBLIC_URL=https://your-app.up.railway.app WEBHOOK_PATH=/webhook PORT=8080 python bot.py
```

Health check: `GET /health`.
