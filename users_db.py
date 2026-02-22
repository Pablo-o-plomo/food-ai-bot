import json
import os

DB_FILE = "users.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_food(user_id, calories, protein, fat, carbs):
    db = load_db()

    user_id = str(user_id)

    if user_id not in db:
        db[user_id] = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0
        }

    db[user_id]["calories"] += float(calories)
    db[user_id]["protein"] += float(protein)
    db[user_id]["fat"] += float(fat)
    db[user_id]["carbs"] += float(carbs)

    save_db(db)


def get_day(user_id):
    db = load_db()
    return db.get(str(user_id), {"calories":0,"protein":0,"fat":0,"carbs":0})