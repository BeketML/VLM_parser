from typing import Optional
from openai import OpenAI
from ...config import get_openai_api_key


def get_openai_client() -> Optional[OpenAI]:
    api_key = get_openai_api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


