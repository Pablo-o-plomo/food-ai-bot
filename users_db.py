import json
import os
from datetime import datetime, timedelta

DB_FILE = "users.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def ensure_user(user_id):
    db = load_db()
    user_id = str(user_id)

    if user_id not in db:
        db[user_id] = {
            "user_type": "free",
            "trial_start": datetime.now().isoformat(),
            "trial_used": False,
            "subscription_end": None,
            "mode": "text",
            "used_promos": [],
        }
        save_db(db)


def get_user(user_id):
    db = load_db()
    return db.get(str(user_id))


def update_user(user_id, key, value):
    db = load_db()
    user_id = str(user_id)

    if user_id not in db:
        ensure_user(user_id)
        db = load_db()

    db[user_id][key] = value
    save_db(db)


def is_trial_active(user):
    if user.get("trial_used"):
        return False
    start = datetime.fromisoformat(user["trial_start"])
    return datetime.now() - start < timedelta(days=3)


def is_subscription_active(user):
    end_raw = user.get("subscription_end")
    if not end_raw:
        return False
    end = datetime.fromisoformat(end_raw)
    return datetime.now() < end