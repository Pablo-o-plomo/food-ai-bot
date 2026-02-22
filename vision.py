from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_food(image_path):

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Определи что это за еда. Напиши: название блюда, примерные калории и БЖУ."},
                    {
                        "type": "input_image",
                        "image": image_bytes
                    }
                ],
            }
        ],
    )

    return response.output_text