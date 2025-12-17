"""Обработчик PDF файлов."""
import os
import time
import fitz
import logging
from typing import Dict, Optional, Any, List
from pathlib import Path

from config.settings import DEFAULT_DPI
from src.utils.page_analyzer import analyze_page
from src.utils.cost_calculator import get_model_cost
from src.parsers.pymupdf_parser import PyMuPDFParser
from src.parsers.vlm_parser import VLMParser
from src.llm.bedrock_client import BedrockClient
from src.output.writers import OutputWriter

logger = logging.getLogger(__name__)

def select_parser(page_analysis: Dict[str, Any], has_tables: bool = False) -> str:
    """Выбирает парсер на основе анализа страницы согласно ТЗ."""
    if page_analysis["has_almost_no_text"]:
        return "vlm"
    if page_analysis["is_image_based"]:
        return "vlm"
    if has_tables:
        return "vlm"
    return "pymupdf"

class PDFProcessor:
    """Процессор для обработки PDF файлов."""
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None):
        """Инициализация процессора."""
        self.bedrock_client = bedrock_client or BedrockClient()
        self.pymupdf_parser = PyMuPDFParser()
        self.vlm_parser = VLMParser(self.bedrock_client)
    
    def process(
        self,
        pdf_path: str,
        output_dir: str,
        page_index: Optional[int] = None,
        dpi: int = DEFAULT_DPI
    ) -> Dict[str, Any]:
        """Обрабатывает PDF файл и возвращает результаты."""
        logger.info(f"Обработка PDF: {pdf_path}")
        
        pdf_doc = fitz.open(pdf_path)
        total_pages = len(pdf_doc)
        
        if page_index is not None:
            if page_index < 1 or page_index > total_pages:
                logger.error(f"Номер страницы {page_index} вне диапазона [1, {total_pages}]")
                pdf_doc.close()
                return {}
            page_indices = [page_index - 1]
        else:
            page_indices = list(range(total_pages))
        
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        pages_data = []
        previous_page_text = ""
        total_tokens = 0
        total_time = 0.0
        total_cost = 0.0
        
        for idx in page_indices:
            page = pdf_doc.load_page(idx)
            page_num = idx + 1
            
            logger.info(f"Обработка страницы {page_num}/{total_pages}")
            
            # Анализ страницы
            analysis = analyze_page(page)
            
            # Рендеринг изображения (если может понадобиться для VLM)
            pix = page.get_pixmap(matrix=mat)
            image_bytes = pix.tobytes("png")
            
            # Классификация через VLM для определения наличия таблиц/диаграмм
            # Если страница image-based или почти без текста, используем VLM без классификации
            has_tables = False
            classifier_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            
            # Классификатор используем для страниц с достаточным текстом и не image-based
            # Это экономит токены, так как image-based страницы все равно требуют VLM
            should_classify = not analysis["has_almost_no_text"] and not analysis["is_image_based"]
            
            if should_classify:
                logger.info(f"Страница {page_num}: запуск классификации (text_length={analysis['text_length']}, is_image_based={analysis['is_image_based']}, has_images={analysis['has_images']})")
                try:
                    has_tables, classifier_usage = self.vlm_parser.classify_page(image_bytes)
                    logger.info(f"Страница {page_num}: классификация завершена, has_tables={has_tables}, tokens={classifier_usage.get('total_tokens', 0)}")
                    time.sleep(0.2)  # Задержка между запросами
                except Exception as e:
                    logger.warning(f"Ошибка классификации страницы {page_num}: {e}")
                    # При ошибке классификации для подозрительных страниц используем VLM как fallback
                    # Если страница имеет изображения, но мало текста, вероятно нужен VLM
                    if analysis["has_images"] and analysis["text_length"] < 500:
                        logger.info(f"Страница {page_num}: fallback на VLM из-за ошибки классификации")
                        has_tables = True
            else:
                logger.info(f"Страница {page_num}: классификация пропущена (has_almost_no_text={analysis['has_almost_no_text']}, is_image_based={analysis['is_image_based']}, text_length={analysis['text_length']})")
            
            # Выбор парсера
            parser_type = select_parser(analysis, has_tables)
            logger.info(f"Страница {page_num}: выбран парсер {parser_type}")
            
            # Парсинг
            if parser_type == "pymupdf":
                content, parser_usage, elapsed = self.pymupdf_parser.parse(page)
            else:
                content, parser_usage, elapsed = self.vlm_parser.extract_text(image_bytes, previous_page_text)
            
            # Суммируем токены классификации и парсинга
            total_page_tokens = classifier_usage.get("total_tokens", 0) + parser_usage.get("total_tokens", 0)
            total_tokens += total_page_tokens
            
            total_time += elapsed
            
            # Учитываем токены классификации и парсинга при расчете стоимости
            total_prompt_tokens = classifier_usage.get("prompt_tokens", 0) + parser_usage.get("prompt_tokens", 0)
            total_completion_tokens = classifier_usage.get("completion_tokens", 0) + parser_usage.get("completion_tokens", 0)
            page_cost = get_model_cost(total_prompt_tokens, total_completion_tokens)
            total_cost += page_cost
            
            pages_data.append({
                "page": page_num,
                "parser": parser_type,
                "tokens": total_page_tokens,
                "classifier_tokens": classifier_usage.get("total_tokens", 0),
                "parser_tokens": parser_usage.get("total_tokens", 0),
                "time_sec": round(elapsed, 2),
                "content": content,
            })
            
            previous_page_text = content
        
        pdf_doc.close()
        
        return {
            "file": os.path.basename(pdf_path),
            "total_pages": len(page_indices),
            "total_tokens": total_tokens,
            "total_time_sec": round(total_time, 2),
            "total_cost_usd": round(total_cost, 6),
            "pages": [
                {
                    "page": p["page"],
                    "parser": p["parser"],
                    "tokens": p["tokens"],
                    "classifier_tokens": p.get("classifier_tokens", 0),
                    "parser_tokens": p.get("parser_tokens", 0),
                    "time_sec": p["time_sec"],
                }
                for p in pages_data
            ],
            "pages_content": pages_data,
        }
    
    def process_directory(
        self,
        dir_path: str,
        output_base_dir: str,
        page_index: Optional[int] = None
    ) -> None:
        """Обрабатывает все PDF файлы в директории."""
        pdf_files = []
        
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        pdf_files.sort()
        
        if not pdf_files:
            logger.warning(f"PDF файлы не найдены в {dir_path}")
            return
        
        logger.info(f"Найдено {len(pdf_files)} PDF файлов")
        
        for pdf_path in pdf_files:
            try:
                pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
                pdf_output_dir = os.path.join(output_base_dir, pdf_name)
                os.makedirs(pdf_output_dir, exist_ok=True)
                
                results = self.process(pdf_path, pdf_output_dir, page_index=page_index)
                if results:
                    from src.output.writers import OutputWriter
                    writer = OutputWriter()
                    writer.write_outputs(results, pdf_output_dir)
            except Exception as e:
                logger.error(f"Ошибка обработки {pdf_path}: {e}")

