import os
import tempfile
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def transcribe_ogg(ogg_bytes: bytes) -> str:
    """
    Telegram voice = OGG/OPUS. Отдаём в транскрипцию.
    """
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(ogg_bytes)
        path = f.name

    try:
        with open(path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
            )
        return (result.text or "").strip()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass