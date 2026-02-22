import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def coach_chat(user_message: str) -> str:
    """
    Чат с коучем по питанию / дисциплине
    """

    system_prompt = """
    Ты строгий, но поддерживающий коуч по питанию и дисциплине.
    Говори коротко, по делу.
    Не сюсюкай.
    Если человек оправдывается — мягко возвращай к ответственности.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.6,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Ошибка коуча: {e}"