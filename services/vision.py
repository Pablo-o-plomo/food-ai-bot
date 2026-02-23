import os
import base64
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VISION_SYSTEM = """
Распознай еду на фото.
Ответ:
1) Что на фото (коротко)
2) Оценка порции
3) Примерные ккал и БЖУ (оценочно)
Без markdown, без звездочек.
Если не еда — так и скажи.
"""

def analyze_food_photo(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Распознай еду на фото."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()