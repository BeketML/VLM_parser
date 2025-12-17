"""PyMuPDF парсер для текстовых страниц."""
import time
import fitz
from typing import Tuple, Dict


class PyMuPDFParser:
    """Быстрый текстовый парсер через PyMuPDF."""
    
    @staticmethod
    def parse(page: fitz.Page) -> Tuple[str, Dict[str, int], float]:
        """Парсит страницу через PyMuPDF."""
        start_time = time.time()
        text = page.get_text("text") or ""
        elapsed = time.time() - start_time
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return text.strip(), usage, elapsed

