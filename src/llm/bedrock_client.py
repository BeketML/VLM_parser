"""Клиент для работы с AWS Bedrock."""
import boto3
import instructor
from typing import Optional

from config.settings import REGION, MODEL_NAME


class BedrockClient:
    """Клиент для работы с AWS Bedrock через boto3 и instructor."""
    
    def __init__(self, region: Optional[str] = None):
        """Инициализация клиента."""
        self.region = region or REGION
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region
        )
        self.instructor_client = instructor.from_provider(
            f"bedrock/{MODEL_NAME}",
            region_name=self.region
        )
    
    @property
    def runtime_client(self):
        """Возвращает boto3 bedrock-runtime клиент."""
        return self.bedrock_runtime
    
    @property
    def instructor(self):
        """Возвращает instructor клиент для structured output."""
        return self.instructor_client

