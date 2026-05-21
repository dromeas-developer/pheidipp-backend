from app.core.llm import get_litellm_client


def get_llm():
    return get_litellm_client()