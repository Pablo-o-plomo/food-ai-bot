from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Ты персональная система контроля питания Павла Кузнецова.
Шеф. Цифры. Питание без лишней воды.

Правила:
- Отвечай коротко
- Без звездочек и markdown
- Без технических пояснений
- По делу
"""

# Память в рамках запущенного процесса
USER_MEMORY = {}

MAX_HISTORY = 10


def generate_text(user_id, user_text):

    if user_id not in USER_MEMORY:
        USER_MEMORY[user_id] = []

    history = USER_MEMORY[user_id]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # добавляем прошлый контекст
    for msg in history:
        messages.append(msg)

    # новое сообщение
    messages.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )

    answer = response.choices[0].message.content

    # сохраняем в память
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": answer})

    # ограничиваем историю
    USER_MEMORY[user_id] = history[-MAX_HISTORY:]

    return answer


def generate_voice(text, voice_style):
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice_style,
        input=text[:300]
    )
    return speech.read()