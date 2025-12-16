import os
from dotenv import load_dotenv

# Load environment variables from .env once at import time
load_dotenv()

# Default model name used by the VLM analyzer
MODEL_NAME: str = os.getenv("VLM_MODEL_NAME", "gpt-4.1-mini")

# Default output directories may be provided by the caller; keep only constants here

def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or None


