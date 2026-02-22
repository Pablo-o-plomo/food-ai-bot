import json
import os
from datetime import date

DB_FILE = "users.json"


def _today():
    return date.today().isoformat()


def _load():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def ensure_user(user_id: int):
    db = _load()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "ui": {"section": "home", "await": None, "wizard": None},
            "goal": None,
            "profile": {},
            "days": {}
        }
        _save(db)


# ---------- UI state ----------
def get_ui(user_id: int) -> dict:
    ensure_user(user_id)
    db = _load()
    return db[str(user_id)].get("ui", {"section": "home", "await": None, "wizard": None})


def set_ui(user_id: int, section=None, await_kind=None, wizard=None):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    ui = db[uid].get("ui", {"section": "home", "await": None, "wizard": None})

    if section is not None:
        ui["section"] = section
    if await_kind is not None:
        ui["await"] = await_kind
    if wizard is not None:
        ui["wizard"] = wizard

    db[uid]["ui"] = ui
    _save(db)


def clear_ui_await(user_id: int):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    db[uid]["ui"]["await"] = None
    _save(db)


# ---------- Goal ----------
def set_goal(user_id: int, goal: str):
    ensure_user(user_id)
    db = _load()
    db[str(user_id)]["goal"] = goal
    _save(db)


def get_goal(user_id: int):
    ensure_user(user_id)
    db = _load()
    return db[str(user_id)].get("goal")


# ---------- Profile ----------
def set_profile_field(user_id: int, key: str, value):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    if "profile" not in db[uid]:
        db[uid]["profile"] = {}
    db[uid]["profile"][key] = value
    _save(db)


def get_profile(user_id: int) -> dict:
    ensure_user(user_id)
    db = _load()
    return db[str(user_id)].get("profile", {})


def is_profile_complete(user_id: int) -> bool:
    p = get_profile(user_id)
    required = ("age", "sex", "height_cm", "weight_kg", "activity_factor")
    return all(k in p for k in required)


# ---------- Day diary ----------
def _ensure_day(db, uid, day):
    if "days" not in db[uid]:
        db[uid]["days"] = {}
    if day not in db[uid]["days"]:
        db[uid]["days"][day] = {
            "calories": 0.0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
            "history": []
        }


def get_day(user_id: int) -> dict:
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    day = _today()
    _ensure_day(db, uid, day)
    _save(db)
    return db[uid]["days"][day]


def add_food(user_id: int, calories: float, protein: float, fat: float, carbs: float):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    day = _today()
    _ensure_day(db, uid, day)

    db[uid]["days"][day]["calories"] += float(calories)
    db[uid]["days"][day]["protein"] += float(protein)
    db[uid]["days"][day]["fat"] += float(fat)
    db[uid]["days"][day]["carbs"] += float(carbs)

    db[uid]["days"][day]["history"].append({
        "calories": float(calories),
        "protein": float(protein),
        "fat": float(fat),
        "carbs": float(carbs)
    })

    _save(db)


def undo_last(user_id: int):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    day = _today()
    _ensure_day(db, uid, day)

    hist = db[uid]["days"][day]["history"]
    if not hist:
        return None

    last = hist.pop()
    db[uid]["days"][day]["calories"] -= last["calories"]
    db[uid]["days"][day]["protein"] -= last["protein"]
    db[uid]["days"][day]["fat"] -= last["fat"]
    db[uid]["days"][day]["carbs"] -= last["carbs"]

    _save(db)
    return db[uid]["days"][day]


def reset_day(user_id: int):
    ensure_user(user_id)
    db = _load()
    uid = str(user_id)
    day = _today()
    db[uid]["days"][day] = {
        "calories": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
        "history": []
    }
    _save(db)