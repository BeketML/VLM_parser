"""Retry логика с экспоненциальной задержкой."""
import time
import logging
from typing import Callable, TypeVar, Optional
from botocore.exceptions import ClientError

from config.settings import MAX_RETRIES, BASE_DELAY

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_exponential_backoff(
    func: Callable[[], T],
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    operation_name: str = "operation"
) -> T:
    """
    Выполняет функцию с retry логикой и экспоненциальной задержкой.
    
    Args:
        func: Функция для выполнения
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        operation_name: Имя операции для логирования
    
    Returns:
        Результат выполнения функции
    """
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"ThrottlingException", "TooManyRequestsException"} or status == 429:
                sleep_s = base_delay * (2 ** attempt)
                logger.warning(f"{operation_name} throttled (attempt {attempt+1}/{max_retries}). Sleeping {sleep_s:.1f}s...")
                time.sleep(sleep_s)
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_s = base_delay * (2 ** attempt)
                logger.warning(f"{operation_name} failed (attempt {attempt+1}/{max_retries}). Sleeping {sleep_s:.1f}s... Error: {e}")
                time.sleep(sleep_s)
                continue
            logger.error(f"{operation_name} failed after {max_retries} attempts: {e}")
            raise
    
    raise RuntimeError(f"{operation_name} failed after {max_retries} retries")

