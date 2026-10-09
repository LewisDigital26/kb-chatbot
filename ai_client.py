"""
ai_client.py - shared Gemini connection with retries, used by every other file.
"""
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()
client = genai.Client()  # reads GEMINI_API_KEY from .env

EMBED_MODEL = "gemini-embedding-001"
# Lite model first (faster, less busy), full model as a backup
CHAT_MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest"]


def with_retries(call, *args, **kwargs):
    """Run an API call, waiting and retrying if Google is busy (503) or rate-limited (429)."""
    for attempt in range(1, 6):
        try:
            return call(*args, **kwargs)
        except (errors.ServerError, errors.ClientError) as e:
            if getattr(e, "code", None) in (429, 500, 503) and attempt < 5:
                wait = attempt * 5
                print(f"    Google busy (error {e.code}), waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def embed(texts: list[str], task: str) -> list[list[float]]:
    """Turn texts into embeddings (lists of numbers that capture meaning).
    task is RETRIEVAL_DOCUMENT for stored chunks, RETRIEVAL_QUERY for questions."""
    vectors = []
    for start in range(0, len(texts), 50):  # send in batches
        batch = texts[start:start + 50]
        result = with_retries(client.models.embed_content, model=EMBED_MODEL,
                              contents=batch, config={"task_type": task})
        vectors.extend(e.values for e in result.embeddings)
    return vectors


def generate_json(prompt: str) -> str:
    """Ask the chat model for a JSON answer, falling back to the second model if the first is busy."""
    last_error = None
    for model in CHAT_MODELS:
        try:
            response = with_retries(
                client.models.generate_content, model=model, contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0},
            )
            return response.text
        except (errors.ServerError, errors.ClientError) as e:
            last_error = e
            print(f"    {model} unavailable, trying the next model...")
    raise RuntimeError(f"All AI models are busy right now: {last_error}")
