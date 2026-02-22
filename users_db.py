import json
import os
from datetime import date

DB_FILE = "users.json"


# ---------- базовые функции ----------
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def today_key():
    return date.today().isoformat()


def ensure_user(user_id):
    db = load_db()
    uid = str(user_id)

    if uid not in db:
        db[uid] = {
            "days": {}
        }
        save_db(db)


# ---------- получить день ----------
def get_day(user_id):
    ensure_user(user_id)

    db = load_db()
    uid = str(user_id)
    day = today_key()

    if day not in db[uid]["days"]:
        db[uid]["days"][day] = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
            "history": []
        }
        save_db(db)

    return db[uid]["days"][day]


# ---------- добавить еду ----------
def add_food(user_id, calories, protein, fat, carbs):
    ensure_user(user_id)

    db = load_db()
    uid = str(user_id)
    day = today_key()

    if day not in db[uid]["days"]:
        db[uid]["days"][day] = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
            "history": []
        }

    db[uid]["days"][day]["calories"] += calories
    db[uid]["days"][day]["protein"] += protein
    db[uid]["days"][day]["fat"] += fat
    db[uid]["days"][day]["carbs"] += carbs

    # сохраняем историю (чтобы можно было отменять)
    db[uid]["days"][day]["history"].append({
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbs": carbs
    })

    save_db(db)


# ---------- отменить последний приём пищи ----------
def undo_last(user_id):
    ensure_user(user_id)

    db = load_db()
    uid = str(user_id)
    day = today_key()

    if day not in db[uid]["days"]:
        return None

    history = db[uid]["days"][day]["history"]

    if not history:
        return None

    last = history.pop()

    db[uid]["days"][day]["calories"] -= last["calories"]
    db[uid]["days"][day]["protein"] -= last["protein"]
    db[uid]["days"][day]["fat"] -= last["fat"]
    db[uid]["days"][day]["carbs"] -= last["carbs"]

    save_db(db)
    return db[uid]["days"][day]


# ---------- обнулить день ----------
def reset_day(user_id):
    ensure_user(user_id)

    db = load_db()
    uid = str(user_id)
    day = today_key()

    db[uid]["days"][day] = {
        "calories": 0,
        "protein": 0,
        "fat": 0,
        "carbs": 0,
        "history": []
    }

    save_db(db)