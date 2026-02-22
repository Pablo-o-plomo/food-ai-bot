import os
from openai import OpenAI

client = OpenAI(api_key="")

while True:
    user = input("Ты: ")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты помощник программиста. Переводи запрос пользователя в ОДНУ команду Windows CMD. Без объяснений."},
            {"role": "user", "content": user}
        ]
    )

    cmd_command = response.choices[0].message.content
    print("Команда:", cmd_command)

    os.system(cmd_command)