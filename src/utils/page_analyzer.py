"""Анализ страниц PDF."""
import fitz
from typing import Dict, Any
from config.settings import MIN_TEXT_LENGTH


def analyze_page(page: fitz.Page) -> Dict[str, Any]:
    """Анализирует страницу PDF и возвращает характеристики."""
    text = page.get_text("text") or ""
    text_length = len(text.strip())
    
    images = page.get_images()
    has_images = len(images) > 0
    
    # Плотность текста (символов на единицу площади)
    rect = page.rect
    area = rect.width * rect.height
    text_density = text_length / area if area > 0 else 0
    
    # Признаки image-based текста (мало текста, но есть изображения)
    is_image_based = text_length < MIN_TEXT_LENGTH and has_images
    
    return {
        "text": text,
        "text_length": text_length,
        "has_images": has_images,
        "text_density": text_density,
        "is_image_based": is_image_based,
        "has_almost_no_text": text_length < MIN_TEXT_LENGTH,
    }

