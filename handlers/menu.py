from telegram import ReplyKeyboardMarkup

def main_menu():
    keyboard = [
        ["🎙 Голосовой режим", "💬 Текстовый режим"],
        ["🔥 Активировать PRO"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def pro_menu():
    keyboard = [
        ["💳 Оплатить PRO"],
        ["🎟 Ввести промокод"],
        ["⬅️ Назад"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)