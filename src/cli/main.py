"""CLI интерфейс для парсера PDF."""
import argparse
import logging
import os

from config.settings import REGION
from src.processors.pdf_processor import PDFProcessor
from src.output.writers import OutputWriter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(
        description="CLI-парсер PDF-документов с использованием VLM и PyMuPDF",
        prog="bedrock-parser"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    parse_parser = subparsers.add_parser("parse", help="Парсить PDF файл или директорию")
    parse_parser.add_argument("path", help="Путь к PDF файлу или директории")
    parse_parser.add_argument("--page", type=int, help="Номер страницы для выборочного парсинга (1-based)")
    parse_parser.add_argument("--output", "-o", default="./output", help="Директория для выходных файлов (по умолчанию: ./output)")
    
    args = parser.parse_args()
    
    if args.command != "parse":
        parser.print_help()
        return
    
    if not os.path.exists(args.path):
        logger.error(f"Путь не найден: {args.path}")
        return
    
    if not REGION:
        logger.warning(f"Переменная AWS_REGION не установлена, используется значение по умолчанию: {REGION}")
    
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)
    
    processor = PDFProcessor()
    writer = OutputWriter()
    
    if os.path.isfile(args.path):
        if not args.path.lower().endswith('.pdf'):
            logger.error("Файл должен быть PDF")
            return
        
        results = processor.process(args.path, output_dir, page_index=args.page)
        if results:
            writer.write_outputs(results, output_dir)
    elif os.path.isdir(args.path):
        processor.process_directory(args.path, output_dir, page_index=args.page)
    else:
        logger.error(f"Неизвестный тип пути: {args.path}")

