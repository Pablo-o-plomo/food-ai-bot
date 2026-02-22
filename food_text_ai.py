import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_text_food(user_text):

    prompt = f"""
Пользователь описал съеденную еду: "{user_text}"

Твоя задача:
1) определить продукты
2) оценить примерный вес
3) посчитать калории и БЖУ

Ответ верни СТРОГО в формате:

Название:
Калории: число
Белки: число
Жиры: число
Углеводы: число

Без лишнего текста.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text