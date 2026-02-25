import os
print("DEBUG OPENAI:", os.getenv("OPENAI_API_KEY"))
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Ты — помощник по питанию в стиле Павла Кузнецова: шеф, цифры, по делу.

Правила:
- Пиши без markdown, без звездочек, без хештегов
- Коротко, ясно
- Без технических пояснений
"""

# Память на время работы процесса (MVP)
USER_MEMORY = {}
MAX_HISTORY = 12  # 6 пар user/assistant

VOICE_NAME = "alloy"  # один приятный голос (фикс)


def generate_text(user_id: int, user_text: str) -> str:
    if user_id not in USER_MEMORY:
        USER_MEMORY[user_id] = []

    history = USER_MEMORY[user_id]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.6,
    )

    answer = (resp.choices[0].message.content or "").strip()

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": answer})
    USER_MEMORY[user_id] = history[-MAX_HISTORY:]

    return answer


def generate_voice_bytes(text: str) -> bytes:
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=VOICE_NAME,
        input=(text or "")[:260],  # коротко в голосе
    )
    return speech.read()
