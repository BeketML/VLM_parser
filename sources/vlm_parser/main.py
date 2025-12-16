import argparse
import logging
import os

# Support running both as a package (python -m parsers_chunkers.vlm_parser.main)
# and directly as a script from this folder (python main.py)
try:
    from .src.extractor import extract_slides_vlm, process_pdf_folder
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from vlm_parser.src.extractor import extract_slides_vlm, process_pdf_folder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="VLM PDF extractor")
    parser.add_argument("--input", required=True, help="Path to PDF file or folder with PDFs")
    parser.add_argument("--out", required=True, help="Results directory")
    parser.add_argument("--folder", action="store_true", help="Process all PDFs in folder (recursive)")
    parser.add_argument("--bedrock", action="store_true", help="Use Bedrock instead of OpenAI")
    args = parser.parse_args()

    # Bedrock env validation
    if args.bedrock:
        region = os.getenv("AWS_REGION")
        model_id = os.getenv("VLM_MODEL_NAME")
        if not region:
            logger.error("Для --bedrock требуется переменная AWS_REGION или REGION")
            return
        if not model_id or ("gpt-" in model_id):
            logger.error("Для --bedrock MODEL_NAME/VLM_MODEL_NAME должен быть Bedrock modelId (например anthropic.claude-...).")
            return

    # Проверяем существование входного пути
    if not os.path.exists(args.input):
        logger.error(f"Путь не найден: {args.input}")
        return

    # Создаем выходную директорию
    os.makedirs(args.out, exist_ok=True)

    if args.folder or os.path.isdir(args.input):
        # Обрабатываем папку
        logger.info(f"Обработка папки: {args.input}")
        summary = process_pdf_folder(args.input, args.out, use_bedrock=args.bedrock)
        logger.info(f"Обработано файлов: {summary['processed_successfully']}/{summary['total_files']}")
    else:
        # Обрабатываем один файл
        if not args.input.lower().endswith('.pdf'):
            logger.error("Файл должен быть PDF")
            return
        
        logger.info(f"Обработка PDF файла: {args.input}")
        slides = extract_slides_vlm(args.input, args.out, use_bedrock=args.bedrock)
        logger.info(f"Обработано страниц: {len(slides)}")


if __name__ == "__main__":
    main()


