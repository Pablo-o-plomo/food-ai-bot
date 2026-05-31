from users_db import is_subscription_active


def has_pro(user) -> bool:
    return is_subscription_active(user)
