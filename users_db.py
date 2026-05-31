import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# Railway injects variables into the real process environment. Load a local
# .env only as a development fallback and never override production env values.
load_dotenv(override=False)


class DatabaseNotConfigured(RuntimeError):
    pass


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _database_url() -> str:
    _debug_database_env()

    for name in (
        "DATABASE_URL",
        "DATABASE_PRIVATE_URL",
        "DATABASE_PUBLIC_URL",
        "POSTGRES_URL",
        "POSTGRES_PRIVATE_URL",
        "POSTGRES_PUBLIC_URL",
        "POSTGRES_DATABASE_URL",
        "RAILWAY_DATABASE_URL",
    ):
        url = _env(name)
        if url:
            return url

    discovered_url = _discover_database_url_from_env()
    if discovered_url:
        return discovered_url

    conninfo = _database_conninfo_from_pg_vars()
    if conninfo:
        return conninfo

    present = ", ".join(_database_env_keys()) or "none"
    raise DatabaseNotConfigured(
        "DATABASE_URL is required. Railway must provide DATABASE_URL or PGHOST/PGUSER/"
        f"PGPASSWORD/PGDATABASE. Present database-related env keys: {present}"
    )


def _discover_database_url_from_env() -> str | None:
    for key in _database_env_keys():
        if key == "DATABASE_URL":
            continue
        if key.endswith("DATABASE_URL") or key.endswith("POSTGRES_URL"):
            url = _env(key)
            if url:
                return url
    return None


def _database_conninfo_from_pg_vars() -> str | None:
    host = _env("PGHOST")
    user = _env("PGUSER")
    password = _env("PGPASSWORD")
    dbname = _env("PGDATABASE") or _env("POSTGRES_DB")
    if not all((host, user, password, dbname)):
        return None

    kwargs = {
        "host": host,
        "user": user,
        "password": password,
        "dbname": dbname,
        "port": _env("PGPORT") or "5432",
    }
    sslmode = _env("PGSSLMODE")
    if sslmode:
        kwargs["sslmode"] = sslmode
    return make_conninfo(**kwargs)


def _database_env_keys() -> list[str]:
    return sorted(key for key in os.environ if "DATABASE" in key or "POSTGRES" in key or key.startswith("PG"))


def _debug_database_env() -> None:
    if _env("DEBUG_DATABASE_ENV") != "1":
        return
    log_database_environment_diagnostics()


def log_database_environment_diagnostics() -> None:
    database_url = os.getenv("DATABASE_URL")
    print("os.environ.keys():", os.environ.keys())
    print('os.getenv("DATABASE_URL"):', "<set>" if database_url else None)
    print("DATABASE env keys:", _database_env_keys())


def database_config_error() -> str | None:
    try:
        _database_url()
    except DatabaseNotConfigured as exc:
        return str(exc)
    return None


def is_database_configured() -> bool:
    return database_config_error() is None


@contextmanager
def get_conn():
    with psycopg.connect(_database_url(), row_factory=dict_row) as conn:
        yield conn


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    user_type TEXT NOT NULL DEFAULT 'free',
                    trial_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    trial_used BOOLEAN NOT NULL DEFAULT FALSE,
                    subscription_end TIMESTAMPTZ,
                    mode TEXT NOT NULL DEFAULT 'text',
                    used_promos TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                    photo_limit_date DATE,
                    photo_count_today INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_limit_date DATE")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_count_today INTEGER NOT NULL DEFAULT 0")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT,
                    age INTEGER,
                    sex TEXT,
                    height_cm NUMERIC(6,2),
                    weight_kg NUMERIC(6,2),
                    goal TEXT,
                    activity_factor NUMERIC(4,2),
                    food_restrictions TEXT,
                    daily_calories NUMERIC(8,2),
                    daily_protein NUMERIC(8,2),
                    daily_fat NUMERIC(8,2),
                    daily_carbs NUMERIC(8,2),
                    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS food_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    eaten_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    log_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    dish_name TEXT NOT NULL,
                    calories NUMERIC(8,2) NOT NULL DEFAULT 0,
                    protein NUMERIC(8,2) NOT NULL DEFAULT 0,
                    fat NUMERIC(8,2) NOT NULL DEFAULT 0,
                    carbs NUMERIC(8,2) NOT NULL DEFAULT 0,
                    raw_ai_response TEXT,
                    source TEXT NOT NULL CHECK (source IN ('photo', 'text', 'voice')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_food_logs_user_date ON food_logs(user_id, log_date DESC)"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    telegram_payment_charge_id TEXT,
                    provider_payment_charge_id TEXT,
                    currency TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    payload TEXT,
                    status TEXT NOT NULL DEFAULT 'successful',
                    raw_payment JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    payment_id BIGINT REFERENCES payments(id) ON DELETE SET NULL,
                    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    ends_at TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()


def ensure_user(user_id: int, tg_user: Any | None = None) -> None:
    username = getattr(tg_user, "username", None) if tg_user else None
    first_name = getattr(tg_user, "first_name", None) if tg_user else None
    last_name = getattr(tg_user, "last_name", None) if tg_user else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = COALESCE(EXCLUDED.username, users.username),
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                    updated_at = NOW()
                """,
                (user_id, username, first_name, last_name),
            )
        conn.commit()


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
            user = cur.fetchone()
    if not user:
        return None
    return _normalize_user(user)


def get_internal_user_id(user_id: int) -> int:
    ensure_user(user_id)
    user = get_user(user_id)
    return int(user["id"])


def update_user(user_id: int, key: str, value: Any) -> None:
    allowed = {"user_type", "trial_start", "trial_used", "subscription_end", "mode", "used_promos"}
    if key not in allowed:
        raise ValueError(f"Unsupported users field: {key}")
    ensure_user(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {key} = %s, updated_at = NOW() WHERE telegram_id = %s", (value, user_id))
        conn.commit()


def save_profile(user_id: int, profile: dict) -> None:
    internal_id = get_internal_user_id(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (
                    user_id, name, age, sex, height_cm, weight_kg, goal, activity_factor,
                    food_restrictions, daily_calories, daily_protein, daily_fat, daily_carbs,
                    onboarding_completed
                ) VALUES (%(user_id)s, %(name)s, %(age)s, %(sex)s, %(height_cm)s, %(weight_kg)s,
                    %(goal)s, %(activity_factor)s, %(food_restrictions)s, %(daily_calories)s,
                    %(daily_protein)s, %(daily_fat)s, %(daily_carbs)s, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    age = EXCLUDED.age,
                    sex = EXCLUDED.sex,
                    height_cm = EXCLUDED.height_cm,
                    weight_kg = EXCLUDED.weight_kg,
                    goal = EXCLUDED.goal,
                    activity_factor = EXCLUDED.activity_factor,
                    food_restrictions = EXCLUDED.food_restrictions,
                    daily_calories = EXCLUDED.daily_calories,
                    daily_protein = EXCLUDED.daily_protein,
                    daily_fat = EXCLUDED.daily_fat,
                    daily_carbs = EXCLUDED.daily_carbs,
                    onboarding_completed = TRUE,
                    updated_at = NOW()
                """,
                {"user_id": internal_id, **profile},
            )
        conn.commit()


def get_profile(user_id: int) -> dict | None:
    internal_id = get_internal_user_id(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (internal_id,))
            return cur.fetchone()


def add_food_log(user_id: int, dish_name: str, calories: float, protein: float, fat: float, carbs: float, raw_ai_response: str, source: str) -> int:
    internal_id = get_internal_user_id(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO food_logs (user_id, dish_name, calories, protein, fat, carbs, raw_ai_response, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (internal_id, dish_name, calories, protein, fat, carbs, raw_ai_response, source),
            )
            row = cur.fetchone()
        conn.commit()
    return int(row["id"])


def get_food_logs(user_id: int, days: int = 1) -> list[dict]:
    internal_id = get_internal_user_id(user_id)
    start_date = date.today() - timedelta(days=max(days, 1) - 1)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM food_logs
                WHERE user_id = %s AND log_date >= %s
                ORDER BY eaten_at DESC, id DESC
                """,
                (internal_id, start_date),
            )
            return cur.fetchall()


def consume_photo_quota(user_id: int, limit: int) -> tuple[bool, int]:
    ensure_user(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET photo_limit_date = CURRENT_DATE,
                    photo_count_today = CASE
                        WHEN photo_limit_date = CURRENT_DATE THEN photo_count_today + 1
                        ELSE 1
                    END,
                    updated_at = NOW()
                WHERE telegram_id = %s
                  AND (photo_limit_date IS DISTINCT FROM CURRENT_DATE OR photo_count_today < %s)
                RETURNING photo_count_today
                """,
                (user_id, limit),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return False, limit
    return True, int(row["photo_count_today"])


def count_photo_logs_today(user_id: int) -> int:
    internal_id = get_internal_user_id(user_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM food_logs WHERE user_id = %s AND log_date = CURRENT_DATE AND source = 'photo'",
                (internal_id,),
            )
            row = cur.fetchone()
    return int(row["cnt"])


def record_payment(user_id: int, payment: Any, status: str = "successful") -> int:
    internal_id = get_internal_user_id(user_id)
    raw = payment.to_dict() if hasattr(payment, "to_dict") else {}
    raw_json = json.loads(json.dumps(raw, default=str))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (
                    user_id, telegram_payment_charge_id, provider_payment_charge_id,
                    currency, total_amount, payload, status, raw_payment
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    internal_id,
                    getattr(payment, "telegram_payment_charge_id", None),
                    getattr(payment, "provider_payment_charge_id", None),
                    getattr(payment, "currency", "RUB"),
                    getattr(payment, "total_amount", 0),
                    getattr(payment, "invoice_payload", None),
                    status,
                    Jsonb(raw_json),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return int(row["id"])


def activate_subscription(user_id: int, days: int = 30, payment_id: int | None = None) -> datetime:
    internal_id = get_internal_user_id(user_id)
    now = datetime.now(timezone.utc)
    user = get_user(user_id)
    current_end = _parse_dt(user.get("subscription_end")) if user else None
    starts_at = current_end if current_end and current_end > now else now
    ends_at = starts_at + timedelta(days=days)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions (user_id, payment_id, starts_at, ends_at, status)
                VALUES (%s, %s, %s, %s, 'active')
                """,
                (internal_id, payment_id, starts_at, ends_at),
            )
            cur.execute(
                """
                UPDATE users
                SET subscription_end = %s, trial_used = TRUE, user_type = 'pro', updated_at = NOW()
                WHERE telegram_id = %s
                """,
                (ends_at, user_id),
            )
        conn.commit()
    return ends_at


def is_trial_active(user: dict) -> bool:
    if not user or user.get("trial_used"):
        return False
    start = _parse_dt(user.get("trial_start"))
    return bool(start and datetime.now(timezone.utc) - start < timedelta(days=3))


def is_subscription_active(user: dict) -> bool:
    if not user:
        return False
    end = _parse_dt(user.get("subscription_end"))
    return bool(end and datetime.now(timezone.utc) < end)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize_user(user: dict) -> dict:
    result = dict(user)
    for key in ("trial_start", "subscription_end", "created_at", "updated_at"):
        if result.get(key) is not None and isinstance(result[key], datetime):
            result[key] = result[key].isoformat()
    result["used_promos"] = result.get("used_promos") or []
    return result
