import base64
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_food(image_path):

    with open(image_path, "rb") as img:
        b64_image = base64.b64encode(img.read()).decode("utf-8")

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Определи блюдо на фото. Напиши: название, калории (ккал), белки, жиры, углеводы."},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{b64_image}"
                    },
                ],
            }
        ],
    )

    return response.output_text