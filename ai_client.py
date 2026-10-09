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
