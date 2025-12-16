import fitz  # PyMuPDF
import json
import os

def pdf_to_json(pdf_path: str, json_path: str = None) -> dict:
    """
    Extract text from a PDF file page by page using PyMuPDF
    and return/save JSON with page numbers and content.
    
    :param pdf_path: Path to the PDF file
    :param json_path: Path to save JSON file (optional). If None, saves next to PDF
    :return: dict with page_num and content
    """
    # Open PDF
    doc = fitz.open(pdf_path)
    pages_content = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")  # извлекаем текст
        pages_content.append({
            "page_num": page_num + 1,  # начинаем с 1
            "content": text.strip()
        })

    # Формируем JSON
    result = {"file": os.path.basename(pdf_path), "pages": pages_content}

    # Если путь к JSON не задан → сохраняем рядом с PDF
    if json_path is None:
        json_path = os.path.splitext(pdf_path)[0] + ".json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    return result
