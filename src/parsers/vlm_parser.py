"""VLM парсер для сложных страниц с таблицами и изображениями."""
import base64
import json
import re
import time
import logging
from typing import Tuple, Dict, Optional

from botocore.exceptions import ClientError

from config.settings import MODEL_NAME, REQUEST_DELAY
from config.prompts import VLM_CLASSIFIER_SYSTEM_PROMPT, VLM_EXTRACTION_SYSTEM_PROMPT
from src.llm.bedrock_client import BedrockClient
from src.utils.usage_parser import parse_bedrock_usage
from src.handlers.retry_handler import retry_with_exponential_backoff
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


def clean_extracted_text(text: str) -> str:
    """Очищает извлеченный текст от артефактов и тегов."""
    if not text:
        return ""
    
    # Удаляем теги <document_text>, </document_text> и подобные
    text = re.sub(r'</?document_text>', '', text, flags=re.IGNORECASE)
    
    # Удаляем другие возможные XML/HTML теги, но сохраняем содержимое
    text = re.sub(r'</?current_page>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?previous_page>', '', text, flags=re.IGNORECASE)
    
    # Удаляем markdown code blocks если есть
    text = re.sub(r'```[^\n]*\n', '', text)
    text = re.sub(r'```', '', text)
    
    return text.strip()


class VLMClassifierResult(BaseModel):
    """Результат классификации страницы через VLM."""
    has_table_or_diagram: bool = Field(
        description="Whether the page contains complex tables or diagrams"
    )


class VLMParser:
    """VLM парсер через AWS Bedrock для сложных страниц."""
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None):
        """Инициализация парсера."""
        self.client = bedrock_client or BedrockClient()
        self.model_id = MODEL_NAME
    
    def classify_page(self, image_bytes: bytes) -> Tuple[bool, Dict[str, int]]:
        """
        Классифицирует страницу на наличие таблиц/диаграмм.
        Возвращает (has_table_or_diagram, usage_metrics).
        """
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "system": [{"type": "text", "text": VLM_CLASSIFIER_SYSTEM_PROMPT.strip()}],
            "messages": messages,
            "max_tokens": 1000
        }
        
        def _classify():
            response = self.client.runtime_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                accept="application/json",
                contentType="application/json"
            )
            return response
        
        try:
            response = retry_with_exponential_backoff(
                _classify,
                operation_name="VLM classifier"
            )
            
            response_body = json.loads(response['body'].read().decode('utf-8'))
            usage = parse_bedrock_usage(response_body)
            
            # Парсим ответ для получения результата классификации
            content_blocks = response_body.get('content', [])
            if content_blocks and 'text' in content_blocks[0]:
                response_text = content_blocks[0]['text'].strip()
                # Парсим JSON ответ
                try:
                    # Удаляем markdown code blocks если есть
                    cleaned_text = re.sub(r'```json\s*', '', response_text)
                    cleaned_text = re.sub(r'```\s*', '', cleaned_text)
                    cleaned_text = cleaned_text.strip()
                    
                    # Парсим JSON
                    result_dict = json.loads(cleaned_text)
                    has_table_or_diagram = result_dict.get("has_table_or_diagram", False)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse classifier response as JSON: {e}. Response: {response_text[:200]}")
                    # Fallback: ищем ключевые слова в ответе
                    has_table_or_diagram = "true" in response_text.lower() or '"has_table_or_diagram": true' in response_text
            else:
                logger.warning("Empty response from classifier")
                has_table_or_diagram = False
            
            return has_table_or_diagram, usage
        except Exception as e:
            logger.error(f"Bedrock classifier invocation failed: {e}")
            return False, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    def extract_text(
        self,
        image_bytes: bytes,
        previous_page_text: str = ""
    ) -> Tuple[str, Dict[str, int], float]:
        """
        Извлекает текст из страницы через VLM.
        Возвращает (extracted_text, usage_metrics, elapsed_time).
        """
        start_time = time.time()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        
        previous_text_block = (
            f"\n<previous_page>\n{previous_page_text[:500]}\n</previous_page>"
            if previous_page_text else ""
        )
        user_prompt = f"Extract the text from the current page image.{previous_text_block}"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": user_prompt
                    }
                ]
            }
        ]
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "system": [{"type": "text", "text": VLM_EXTRACTION_SYSTEM_PROMPT}],
            "messages": messages,
            "max_tokens": 9000
        }
        
        def _extract():
            response = self.client.runtime_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                accept="application/json",
                contentType="application/json"
            )
            return response
        
        try:
            response = retry_with_exponential_backoff(
                _extract,
                operation_name="VLM extraction"
            )
            
            response_body = json.loads(response['body'].read().decode('utf-8'))
            usage = parse_bedrock_usage(response_body)
            elapsed = time.time() - start_time
            
            content_blocks = response_body.get('content', [])
            if content_blocks and 'text' in content_blocks[0]:
                extracted_text = content_blocks[0]['text']
                # Очищаем текст от тегов и артефактов
                cleaned_text = clean_extracted_text(extracted_text)
                time.sleep(REQUEST_DELAY)  # Задержка между запросами
                return cleaned_text, usage, elapsed
            return "", usage, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Bedrock extraction invocation failed: {e}")
            raise RuntimeError(f"Bedrock extraction failed: {e}")

