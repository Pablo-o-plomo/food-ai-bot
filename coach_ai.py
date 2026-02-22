import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def coach_reply(nutrition_text, today_stats=None):

    context = ""
    if today_stats:
        context = f"""
Вот текущий прогресс пользователя за сегодня:
Калории: {today_stats['calories']}
Белки: {today_stats['protein']}
Жиры: {today_stats['fat']}
Углеводы: {today_stats['carbs']}
"""

    prompt = f"""
Ты дружелюбный AI-нутрициолог в Telegram.

Правила:
- отвечай по-человечески
- кратко (3-6 строк)
- поддерживающе
- без осуждения
- используй 1-3 уместных эмодзи
- НЕ пиши как врач
- НЕ пиши длинные лекции

Вот данные о приёме пищи:
{nutrition_text}

{context}

Сформируй сообщение пользователю.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text