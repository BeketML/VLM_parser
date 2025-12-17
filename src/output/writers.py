"""Генерация выходных файлов (Markdown и JSON)."""
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OutputWriter:
    """Класс для записи выходных файлов."""
    
    def write_outputs(self, results: Dict[str, Any], output_dir: str) -> None:
        """Генерирует выходные файлы: Markdown и JSON."""
        os.makedirs(output_dir, exist_ok=True)
        
        # JSON с метриками
        metrics = {
            "file": results["file"],
            "total_pages": results["total_pages"],
            "total_tokens": results["total_tokens"],
            "total_time_sec": results["total_time_sec"],
            "total_cost_usd": results["total_cost_usd"],
            "pages": results["pages"],
        }
        
        json_path = os.path.join(output_dir, "metrics.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранен JSON: {json_path}")
        
        # Директория для постраничных MD файлов
        pages_dir = os.path.join(output_dir, "pages")
        os.makedirs(pages_dir, exist_ok=True)
        
        # Постраничные MD файлы и общий MD
        all_content_parts = []
        for page_data in results["pages_content"]:
            page_num = page_data["page"]
            content = page_data["content"].strip() if page_data.get("content") else ""
            
            page_md_path = os.path.join(pages_dir, f"{page_num}.md")
            with open(page_md_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            all_content_parts.append(f"{content}\n")
        
        # Общий Markdown файл: имя совпадает с именем PDF (без расширения)
        base_name, _ = os.path.splitext(results["file"])
        output_md_path = os.path.join(output_dir, f"{base_name}.md")
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_content_parts))
        logger.info(f"Сохранен общий MD: {output_md_path}")

