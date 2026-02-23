from datetime import datetime, timedelta
from users_db import ensure_user, get_user, update_user

# Примеры. Потом сделаем генератор одноразовых кодов.
PROMO_CODES = {
    "KING30": 30,
    "KING365": 365,
}

def apply_promo_code(user_id: int, code: str):
    ensure_user(user_id)
    user = get_user(user_id)

    code = (code or "").upper().strip()
    if not code:
        return False, "Промокод пустой."

    used = user.get("used_promos", [])
    if code in used:
        return False, "Этот промокод уже использован."

    if code not in PROMO_CODES:
        return False, "Промокод недействителен."

    days = PROMO_CODES[code]
    end = (datetime.now() + timedelta(days=days)).isoformat()

    update_user(user_id, "subscription_end", end)
    update_user(user_id, "trial_used", True)

    used.append(code)
    update_user(user_id, "used_promos", used)

    return True, f"🔥 PRO активирован на {days} дней."