"""Конфигурационные настройки проекта."""
import os
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

# AWS настройки
REGION = "eu-central-1"
MODEL_NAME = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_INFERENCE_PROFILE_ARN = "arn:aws:bedrock:eu-central-1:920233773808:inference-profile/eu.anthropic.claude-sonnet-4-20250514-v1:0"

# Цены на токены (USD за 1K токенов) для различных моделей Anthropic
# Актуальные цены на 2025 год
MODEL_PRICES_USD_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    # Claude 4.5 модели
    "anthropic.claude-opus-4-5": {"input": 0.005, "output": 0.025},
    "anthropic.claude-haiku-4-5": {"input": 0.001, "output": 0.005},
    "anthropic.claude-sonnet-4-5": {"input": 0.003, "output": 0.015},
    "anthropic.claude-sonnet-4-5-long-context": {"input": 0.006, "output": 0.0225},
    "eu.anthropic.claude-opus-4-5": {"input": 0.005, "output": 0.025},
    "eu.anthropic.claude-haiku-4-5": {"input": 0.0011, "output": 0.0055},  # EU регион
    "eu.anthropic.claude-sonnet-4-5": {"input": 0.0033, "output": 0.0165},  # EU регион
    "eu.anthropic.claude-sonnet-4-5-long-context": {"input": 0.0066, "output": 0.02475},  # EU регион
    
    # Claude 4 модели
    "anthropic.claude-opus-4": {"input": 0.015, "output": 0.075},
    "anthropic.claude-opus-4-1": {"input": 0.015, "output": 0.075},
    "anthropic.claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "anthropic.claude-sonnet-4-long-context": {"input": 0.006, "output": 0.0225},
    "eu.anthropic.claude-opus-4": {"input": 0.015, "output": 0.075},
    "eu.anthropic.claude-opus-4-1": {"input": 0.015, "output": 0.075},
    "eu.anthropic.claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "eu.anthropic.claude-sonnet-4-20250514-v1:0": {"input": 0.003, "output": 0.015},
    "eu.anthropic.claude-sonnet-4-long-context": {"input": 0.006, "output": 0.0225},
    
    # Claude 3.7 модели
    "anthropic.claude-3-7-sonnet-20250219-v1:0": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-7-sonnet": {"input": 0.003, "output": 0.015},
    "eu.anthropic.claude-3-7-sonnet": {"input": 0.003, "output": 0.015},
    
    # Claude 3.5 модели
    "anthropic.claude-3-5-sonnet-20240620-v1:0": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-5-sonnet-v2": {"input": 0.003, "output": 0.015},
    "eu.anthropic.claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    
    # Claude 3 модели (legacy)
    "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-opus-20240229-v1:0": {"input": 0.015, "output": 0.075},
    "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
    "eu.anthropic.claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "eu.anthropic.claude-3-opus": {"input": 0.015, "output": 0.075},
    "eu.anthropic.claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}

# Порог минимального количества символов для определения "почти нет текста"
MIN_TEXT_LENGTH = 100

# Порог плотности текста для определения необходимости VLM классификации
# Если плотность высокая (>0.1), вероятно простой текст, можно пропустить классификацию
TEXT_DENSITY_THRESHOLD = 0.1

# Настройки обработки
DEFAULT_DPI = 200
MAX_RETRIES = 5
BASE_DELAY = 1.0
REQUEST_DELAY = 0.2  # Задержка между запросами к Bedrock (секунды)

