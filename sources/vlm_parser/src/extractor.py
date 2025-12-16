import os
import json
import logging
from typing import Any, Dict, List, Optional
import time
import os

import fitz  # PyMuPDF

from .analyzer import analyze_slide_vlm, classify_slide_vlm
from .utils.helpers import strip_current_page_tags
from .utils.pricing import get_model_cost_per_pdf, get_model_cost_for_usage
from ..config import MODEL_NAME
from .pdf_parser import pdf_to_json 

logger = logging.getLogger(__name__)


def prepare_output_dirs(results_dir: str) -> (str, str):
    """Создаёт директории для изображений и Markdown"""
    images_dir = os.path.join(results_dir, "images")
    md_dir = os.path.join(results_dir, "md")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)
    return images_dir, md_dir


def render_pdf_pages(pdf_path: str, images_dir: str, dpi: int = 200) -> List[str]:
    """Рендерит PDF в изображения и возвращает пути"""
    doc = fitz.open(pdf_path)
    image_paths = []
    
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            img_filename = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page_{page_num+1}.png"
            img_path = os.path.join(images_dir, img_filename)
            pix.save(img_path)
            image_paths.append(img_path)
            logger.info(f"Сохранили изображение: {img_path}")
    finally:
        doc.close()

    return image_paths


def save_markdown(content: str, md_path: str) -> None:
    """Сохраняет текст в .md файл"""
    try:
        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write(content)
    except Exception as e:
        logger.error(f"Не удалось сохранить Markdown {md_path}: {e}")


def save_json(payload: dict, json_path: str) -> None:
    """Сохраняет JSON с результатами"""
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Не удалось сохранить JSON {json_path}: {e}")


def fallback_result() -> Dict[str, Any]:
    """Результат по умолчанию при ошибке анализа"""
    return {
        "title": "",
        "content": "[ERROR] VLM analysis failed",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

def make_final_payload(
    pdf_path: str,
    results_dir: str,
    images_dir: str,
    md_dir: str,
    slides: List[Dict[str, Any]],
    total_prompt_tokens: int,
    total_completion_tokens: int,
    total_cost_usd: float,
) -> Dict[str, Any]:
    """Формирует итоговый JSON для всего PDF"""
    return {
        "pdf_path": os.path.abspath(pdf_path),
        "total_pages": len(slides),
        "results_dir": os.path.abspath(results_dir),
        "images_dir": os.path.abspath(images_dir),
        "md_dir": os.path.abspath(md_dir),
        "model": MODEL_NAME,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_cost_usd": total_cost_usd,
        "slides": slides,
    }

def extract_slides_vlm(pdf_path: str, results_dir: str, use_bedrock: bool = False) -> List[Dict[str, Any]]:
    logger.info(f"Начинаем обработку PDF: {pdf_path}")
    
    try:
        # Сохраняем промежуточный JSON рядом с результатами, а не у исходного PDF
        interim_json_path = os.path.join(results_dir, f"{os.path.splitext(os.path.basename(pdf_path))[0]}_text.json")
        pdf_json = pdf_to_json(pdf_path, json_path=interim_json_path)
        if pdf_json['pages']:
            logger.info(f"Result of pdf_to_json PyMuPDF: {pdf_json['pages'][0]['content'][:100]}...")
        else:
            logger.warning("PDF не содержит страниц")
            return []
    except Exception as e:
        logger.error(f"Ошибка чтения PDF: {e}")
        return []

    images_dir, md_dir = prepare_output_dirs(results_dir)
    image_paths = render_pdf_pages(pdf_path, images_dir)

    slides = []
    prev_text, prev_img_path = None, None
    total_prompt_tokens, total_completion_tokens = 0, 0

    # Задержка между запросами к провайдеру (мс). По умолчанию 200 мс.
    delay_ms_env = os.getenv("BEDROCK_REQUEST_DELAY_MS") or "200"
    try:
        per_request_delay = max(0, int(delay_ms_env)) / 1000.0
    except ValueError:
        per_request_delay = 0.2

    for page_num, img_path in enumerate(image_paths, start=1):
        logger.info(f"Обрабатываем страницу {page_num}/{len(image_paths)}")
        
        try:
            class_result = classify_slide_vlm(img_path, use_bedrock=use_bedrock)
            logger.info(f"Result of classify_slide_vlm: {class_result}")
            
            if class_result == "true":
                try:
                    llm_result = analyze_slide_vlm(
                        img_path,
                        prev_text=prev_text,
                        prev_img_path=prev_img_path,
                        use_bedrock=use_bedrock,
                    )
                except Exception as e:
                    logger.error(f"[RAG-VLM] Ошибка анализа слайда {page_num}: {e}")
                    llm_result = fallback_result()
            else:
                # Используем текст из PyMuPDF (индекс с 0, но page_num с 1)
                page_content = pdf_json['pages'][page_num - 1]['content']
                llm_result = {
                    "title": "",
                    "content": page_content,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                }
        except Exception as e:
            logger.error(f"Ошибка обработки страницы {page_num}: {e}")
            llm_result = fallback_result()

        # Чистим текст
        content = strip_current_page_tags(llm_result.get("content", ""))

        # Сохраняем .md
        md_path = os.path.join(md_dir, f"{page_num}.md")
        save_markdown(content, md_path)

        # Токены
        slide_usage = llm_result.get("usage", {}) or {}
        slide_prompt_toks = int(slide_usage.get("prompt_tokens", 0) or 0)
        slide_completion_toks = int(slide_usage.get("completion_tokens", 0) or 0)
        total_prompt_tokens += slide_prompt_toks
        total_completion_tokens += slide_completion_toks

        slide_cost = get_model_cost_for_usage(
            model=MODEL_NAME,
            prompt_tokens=slide_prompt_toks,
            completion_tokens=slide_completion_toks,
        )

        slides.append({
            "slide_num": page_num,
            "image_path": img_path,
            "title": llm_result.get("title", ""),
            "content": content,
            "usage": slide_usage,
            "cost_usd": slide_cost,
        })

        prev_text, prev_img_path = content, img_path

        # Пауза между обращениями к модели, чтобы уменьшить риск 429
        if use_bedrock and per_request_delay > 0:
            time.sleep(per_request_delay)

    # Общая стоимость
    total_cost_usd = get_model_cost_per_pdf(
        model=MODEL_NAME,
        total_input_tokens=total_prompt_tokens,
        total_output_tokens=total_completion_tokens,
    )

    payload = make_final_payload(
        pdf_path, results_dir, images_dir, md_dir,
        slides, total_prompt_tokens, total_completion_tokens, total_cost_usd
    )

    json_path = os.path.join(results_dir, f"{os.path.splitext(os.path.basename(pdf_path))[0]}.json")
    save_json(payload, json_path)
    logger.info(f"Сохранили JSON: {json_path}")

    return slides


def find_pdf_files(input_path: str) -> List[str]:
    """Находит все PDF файлы в папке или возвращает один файл"""
    pdf_files = []
    
    if os.path.isfile(input_path):
        if input_path.lower().endswith('.pdf'):
            pdf_files.append(input_path)
    elif os.path.isdir(input_path):
        # Ищем PDF в папке и подпапках
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
    
    return sorted(pdf_files)


def process_pdf_folder(input_path: str, base_output_dir: str, use_bedrock: bool = False) -> Dict[str, Any]:
    """Обрабатывает папку с PDF файлами или один PDF файл"""
    pdf_files = find_pdf_files(input_path)
    
    if not pdf_files:
        logger.warning(f"Не найдено PDF файлов в {input_path}")
        return {"processed_files": [], "errors": []}
    
    logger.info(f"Найдено {len(pdf_files)} PDF файлов для обработки")
    
    processed_files = []
    errors = []
    
    for pdf_file in pdf_files:
        try:
            # Создаем отдельную папку для каждого PDF
            pdf_name = os.path.splitext(os.path.basename(pdf_file))[0]
            pdf_output_dir = os.path.join(base_output_dir, pdf_name)
            os.makedirs(pdf_output_dir, exist_ok=True)
            
            logger.info(f"Обрабатываем PDF: {pdf_file}")
            slides = extract_slides_vlm(pdf_file, pdf_output_dir, use_bedrock=use_bedrock)
            
            processed_files.append({
                "pdf_path": pdf_file,
                "output_dir": pdf_output_dir,
                "slides_count": len(slides),
                "status": "success"
            })
            
        except Exception as e:
            error_msg = f"Ошибка обработки {pdf_file}: {str(e)}"
            logger.error(error_msg)
            errors.append({
                "pdf_path": pdf_file,
                "error": str(e),
                "status": "failed"
            })
    
    # Сохраняем общий отчет
    summary = {
        "input_path": input_path,
        "total_files": len(pdf_files),
        "processed_successfully": len(processed_files),
        "failed": len(errors),
        "processed_files": processed_files,
        "errors": errors
    }
    
    summary_path = os.path.join(base_output_dir, "processing_summary.json")
    save_json(summary, summary_path)
    logger.info(f"Сохранен отчет обработки: {summary_path}")
    
    return summary