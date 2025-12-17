"""Расчет стоимости использования моделей."""
from typing import Optional
from config.settings import MODEL_NAME, MODEL_PRICES_USD_PER_1K_TOKENS


def get_model_cost(prompt_tokens: int, completion_tokens: int, model: Optional[str] = None) -> float:
    """Вычисляет стоимость в USD для использования модели."""
    model_name = model or MODEL_NAME
    prices = MODEL_PRICES_USD_PER_1K_TOKENS.get(model_name)
    if not prices:
        return 0.0
    input_cost = (prompt_tokens / 1000.0) * prices["input"]
    output_cost = (completion_tokens / 1000.0) * prices["output"]
    return round(input_cost + output_cost, 6)

