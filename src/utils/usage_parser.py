"""Парсинг метрик использования из ответов Bedrock."""
from typing import Dict, Any


def parse_bedrock_usage(response_body: Dict[str, Any]) -> Dict[str, int]:
    """Извлекает usage токенов из ответа Bedrock."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    if isinstance(response_body, dict) and isinstance(response_body.get("usage"), dict):
        inp = int(response_body["usage"].get("input_tokens", 0) or 0)
        out = int(response_body["usage"].get("output_tokens", 0) or 0)
        usage["prompt_tokens"] = inp
        usage["completion_tokens"] = out
        usage["total_tokens"] = inp + out
    
    return usage

