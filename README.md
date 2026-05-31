# food-ai-bot

Telegram bot for food recognition, nutrition logging, onboarding, subscriptions and Railway webhook deployment.

## Required environment

- `BOT_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL` — Railway Postgres connection string. If it is absent, the bot can also use Railway/Postgres `DATABASE_PRIVATE_URL`, `DATABASE_PUBLIC_URL`, `POSTGRES_URL`, `POSTGRES_PRIVATE_URL`, `POSTGRES_PUBLIC_URL`, `POSTGRES_DATABASE_URL`, `RAILWAY_DATABASE_URL`, or `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`.

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

For database env debugging, temporarily set `DEBUG_DATABASE_ENV=1`; the bot logs `os.environ.keys()`, the result of `os.getenv("DATABASE_URL")` as `<set>`/`None`, and database-related env key names without printing secret values.

If Railway logs show `Present database-related env keys: none`, the service has no Postgres variables attached. Add a Postgres plugin/service and set `DATABASE_URL` to the Railway variable reference, for example `${{Postgres.DATABASE_URL}}` (use your actual Postgres service name). The bot now starts in degraded mode instead of crash-looping when DB variables are absent, and `/health` reports `database_configured=false`.
