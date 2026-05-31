# food-ai-bot

Telegram bot for food recognition, nutrition logging, onboarding, subscriptions and Railway webhook deployment.

## Required environment

- `BOT_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL` — Railway Postgres connection string. If it is absent, the bot can also use Railway/Postgres `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`.

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

For database env debugging, temporarily set `DEBUG_DATABASE_ENV=1`; the bot logs database-related env key names and whether `DATABASE_URL` is present, without printing secret values.
