from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_litellm_client() -> AsyncOpenAI:
    # Strip trailing slash to ensure base_url matches settings exactly
    base_url = settings.LITELLM_BASE_URL.rstrip("/")
    return AsyncOpenAI(
        api_key=settings.LITELLM_API_KEY,
        base_url=base_url,
    )