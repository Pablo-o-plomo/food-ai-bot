from telegram import ReplyKeyboardMarkup

def main_menu():
    keyboard = [
        ["🎙 Голосовой режим", "💬 Текстовый режим"],
        ["🎧 Выбрать голос"],
        ["🔥 Активировать PRO"],
        ["🎟 Ввести промокод"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)