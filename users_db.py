import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("USERS_DB_PATH", "users_db.json")


def _load() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"users": {}}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: Dict[str, Any]) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_user(user_id: int, username: str = "") -> None:
    data = _load()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "username": username,
            "profile": {
                "age": None,
                "sex": None,        # "m" | "f"
                "height": None,     # cm
                "weight": None,     # kg
                "kcal_target": 2000
            },
            "days": {}
        }
        _save(data)


def get_user(user_id: int) -> Dict[str, Any]:
    data = _load()
    uid = str(user_id)
    return data["users"].get(uid, {})


def set_profile_field(user_id: int, field: str, value: Any) -> None:
    data = _load()
    uid = str(user_id)
    user = data["users"].setdefault(uid, {"profile": {}, "days": {}})
    user.setdefault("profile", {})
    user["profile"][field] = value
    _save(data)


def add_food_entry(user_id: int, text: str, kcal: Optional[int] = None) -> None:
    data = _load()
    uid = str(user_id)
    user = data["users"].setdefault(uid, {"profile": {}, "days": {}})
    days = user.setdefault("days", {})
    today = str(date.today())

    day = days.setdefault(today, {"entries": [], "kcal_total": 0})
    entry = {"text": text, "kcal": kcal}
    day["entries"].append(entry)

    if isinstance(kcal, int) and kcal > 0:
        day["kcal_total"] = int(day.get("kcal_total", 0)) + kcal

    _save(data)


def get_today_summary(user_id: int) -> Dict[str, Any]:
    user = get_user(user_id)
    profile = user.get("profile", {})
    days = user.get("days", {})
    today = str(date.today())
    day = days.get(today, {"entries": [], "kcal_total": 0})

    kcal_target = profile.get("kcal_target") or 2000
    kcal_total = int(day.get("kcal_total", 0) or 0)
    left = int(kcal_target) - kcal_total

    return {
        "entries": day.get("entries", []),
        "kcal_total": kcal_total,
        "kcal_target": int(kcal_target),
        "kcal_left": left
    }


def profile_is_complete(user_id: int) -> bool:
    u = get_user(user_id)
    p = u.get("profile", {})
    return all([
        isinstance(p.get("age"), int),
        p.get("sex") in ("m", "f"),
        isinstance(p.get("height"), int),
        isinstance(p.get("weight"), (int, float)),
        isinstance(p.get("kcal_target"), int),
    ])