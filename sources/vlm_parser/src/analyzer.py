import json
import logging
from typing import Any, Dict, Optional, List
import boto3
import os
import time
from botocore.exceptions import ClientError

from .utils.client import get_openai_client
from .utils.helpers import encode_image_to_b64
from .prompts import PROMPT, CONTEXT_INSTRUCTIONS, CLASSIFIER_PROMPT
from ..config import MODEL_NAME
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

REGION = os.getenv('AWS_REGION')



def build_user_content(
    img_path: str,
    prev_text: Optional[str] = None,
    prev_img_path: Optional[str] = None,
    custom_prompt: str = None
) -> List[Dict[str, Any]]:
    """Формирует контент для отправки в OpenAI."""
    current_image_b64 = encode_image_to_b64(img_path)
    
    # Выбираем prompt: custom или стандартный
    base_prompt = custom_prompt if custom_prompt else PROMPT
    context_instructions = CONTEXT_INSTRUCTIONS if (prev_text or prev_img_path) and not custom_prompt else ""

    user_content = [{"type": "text", "text": base_prompt + context_instructions}]

    if prev_text:
        prev_text_block = f"<previous_text>\n{prev_text}\n</previous_text>"
        user_content.append({"type": "text", "text": prev_text_block})

    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{current_image_b64}"}
    })

    return user_content


def build_bedrock_content(
    img_path: str,
    prev_text: Optional[str] = None,
    prev_img_path: Optional[str] = None,
    custom_prompt: str = None
) -> List[Dict[str, Any]]:
    """Формирует контент в формате Claude Messages для Bedrock."""
    current_image_b64 = encode_image_to_b64(img_path)
    base_prompt = custom_prompt if custom_prompt else PROMPT
    context_instructions = CONTEXT_INSTRUCTIONS if (prev_text or prev_img_path) and not custom_prompt else ""

    content: List[Dict[str, Any]] = [{"type": "text", "text": base_prompt + context_instructions}]
    if prev_text:
        prev_text_block = f"<previous_text>\n{prev_text}\n</previous_text>"
        content.append({"type": "text", "text": prev_text_block})

    content.append({
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": current_image_b64,
        },
    })
    return content


def call_openai(user_content: List[Dict[str, Any]]) -> Any:
    """Делает запрос к OpenAI API и возвращает сырой ответ."""
    client = get_openai_client()
    if client is None:
        raise ValueError("OPENAI_API_KEY не найден.")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=10000,
    )
    return response

def call_bedrock(user_content: List[Dict[str, Any]]) -> Any:
    """Делает запрос к Bedrock API и возвращает сырой ответ."""
    client = boto3.client('bedrock-runtime', region_name=REGION)
    # user_content должен быть в формате Claude Messages blocks (build_bedrock_content)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {"role": "user", "content": user_content}
        ],
        # Можно сделать настраиваемыми:
        "max_tokens": 4000,
    }
    profile_arn = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN") or os.getenv("INFERENCE_PROFILE_ARN")
    # В вашей версии SDK параметр inferenceProfileArn недоступен. Передадим ARN профиля в modelId.
    chosen_id = profile_arn if profile_arn else MODEL_NAME
    # Экспоненциальный бэкофф на случай 429/Throttling
    max_retries = 5
    base_delay = 1.0  # сек
    for attempt in range(max_retries):
        try:
            response = client.invoke_model(
                modelId=chosen_id,
                body=json.dumps(body),
                accept="application/json",
                contentType="application/json",
            )
            return response
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"ThrottlingException", "TooManyRequestsException"} or status == 429:
                sleep_s = base_delay * (2 ** attempt)
                logger.warning(f"Bedrock throttled (attempt {attempt+1}/{max_retries}). Sleeping {sleep_s:.1f}s...")
                time.sleep(sleep_s)
                continue
            raise
        except Exception:
            # Повторяем при временных сетевых ошибках
            sleep_s = base_delay * (2 ** attempt)
            logger.warning(f"Bedrock call failed (attempt {attempt+1}/{max_retries}). Sleeping {sleep_s:.1f}s...")
            time.sleep(sleep_s)
            continue
    # Если все попытки исчерпаны, бросаем последнюю ошибку
    raise RuntimeError("Bedrock invoke_model failed after retries")


def parse_response(response: Any) -> tuple[str, str]:
    """Парсит ответ OpenAI: достает title и content."""
    result_text = response.choices[0].message.content.strip()

    try:
        if result_text.startswith("```"):
            result_text = result_text[result_text.find("{"): result_text.rfind("}") + 1]

        parsed = json.loads(result_text)
        return parsed.get("title", ""), parsed.get("content", "")
    except Exception:
        logger.warning("Не удалось распарсить JSON, сохраняю сырой текст ответа как content")
        return "", result_text


def parse_bedrock_response(response: Any) -> str:
    """Грубый парсер ответа Bedrock → извлекает текст контента.
    Ожидает JSON в body, где текст лежит в поле 'output_text' или аналогичном.
    Возвращает строку контента; заголовок не выделяется отдельно.
    """
    try:
        body = response.get("body") if isinstance(response, dict) else getattr(response, "get", lambda *_: None)("body")
        raw = body.read().decode("utf-8") if hasattr(body, "read") else body
        data = json.loads(raw) if isinstance(raw, str) else {}
        # Claude Messages (Bedrock) обычно возвращает { content: [{type: "text", text: "..."}, ...] }
        if isinstance(data, dict):
            blocks = data.get("content")
            if isinstance(blocks, list):
                texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
                joined = "".join(texts).strip()
                if joined:
                    return joined
            # Fallback на распространённые поля
            if "output_text" in data:
                return str(data["output_text"]).strip()
            if "generation" in data and isinstance(data["generation"], str):
                return data["generation"].strip()
            if "content" in data and isinstance(data["content"], str):
                return data["content"].strip()
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        logger.warning("Не удалось распарсить ответ Bedrock; сохраняю сырой ответ как текст")
        try:
            return str(response)
        except Exception:
            return ""


def parse_bedrock_usage(response: Any) -> Dict[str, int]:
    """Пытаемся извлечь usage для Bedrock.
    1) Сначала ищем в JSON-ответе поля usage.input_tokens / usage.output_tokens
    2) Затем пробуем заголовки HTTP: x-amzn-bedrock-(input|output)-token-count/ ...-tokens
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    # Попытка 1: из body JSON
    try:
        body = response.get("body") if isinstance(response, dict) else getattr(response, "get", lambda *_: None)("body")
        raw = body.read().decode("utf-8") if hasattr(body, "read") else body
        data = json.loads(raw) if isinstance(raw, str) else None
        if isinstance(data, dict) and isinstance(data.get("usage"), dict):
            inp = int(data["usage"].get("input_tokens", 0) or 0)
            out = int(data["usage"].get("output_tokens", 0) or 0)
            usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"] = inp, out, inp + out
            return usage
    except Exception:
        pass

    # Попытка 2: из заголовков HTTP
    try:
        headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {}) if isinstance(response, dict) else {}
        # Варианты имен заголовков
        candidates_in = [
            "x-amzn-bedrock-input-token-count",
            "x-amzn-bedrock-input-tokens",
        ]
        candidates_out = [
            "x-amzn-bedrock-output-token-count",
            "x-amzn-bedrock-output-tokens",
        ]
        inp = next((int(headers[k]) for k in candidates_in if k in headers), 0)
        out = next((int(headers[k]) for k in candidates_out if k in headers), 0)
        usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"] = inp, out, inp + out
    except Exception:
        pass
    return usage

def extract_usage(response: Any) -> Dict[str, int]:
    """Извлекает usage токенов."""
    usage = getattr(response, "usage", None)
    if usage:
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def analyze_slide_vlm(
    img_path: str,
    prev_text: Optional[str] = None,
    prev_img_path: Optional[str] = None,
    use_bedrock: bool = False,
) -> Dict[str, Any]:
    """Главная функция анализа слайда."""
    if use_bedrock:
        user_content = build_bedrock_content(img_path, prev_text, prev_img_path)
        response = call_bedrock(user_content)
        content = parse_bedrock_response(response)
        title = ""
        usage = parse_bedrock_usage(response)
    else:
        user_content = build_user_content(img_path, prev_text, prev_img_path)
        response = call_openai(user_content)
        title, content = parse_response(response)
        usage = extract_usage(response)

    return {"title": title, "content": content, "usage": usage}

def classify_slide_vlm(
    img_path: str,
    prev_text: Optional[str] = None,
    prev_img_path: Optional[str] = None,
    use_bedrock: bool = False,
) -> str:
    """Классифицирует слайд как таблицу или диаграмму."""
    if use_bedrock:
        user_content = build_bedrock_content(img_path, prev_text, prev_img_path, CLASSIFIER_PROMPT)
        response = call_bedrock(user_content)
        text = parse_bedrock_response(response).strip().lower()
        return "true" if text.startswith("true") else "false"
    else:
        user_content = build_user_content(img_path, prev_text, prev_img_path, CLASSIFIER_PROMPT)
        response = call_openai(user_content)
        return response.choices[0].message.content.strip()