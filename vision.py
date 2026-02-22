import base64
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_food(image_path):
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты нутрициолог. Определи блюдо на фото и оцени калорийность. Ответ: название блюда, калории, белки, жиры, углеводы."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Что это за еда?"},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{base64_image}"
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    return response.choices[0].message.content 
