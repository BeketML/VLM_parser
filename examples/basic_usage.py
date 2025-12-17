"""Пример базового использования парсера."""
from src.processors.pdf_processor import PDFProcessor
from src.output.writers import OutputWriter


def main():
    """Пример обработки одного PDF файла."""
    # Инициализация
    processor = PDFProcessor()
    writer = OutputWriter()
    
    # Обработка PDF
    pdf_path = "path/to/your/document.pdf"
    output_dir = "./output"
    
    results = processor.process(pdf_path, output_dir)
    
    if results:
        # Сохранение результатов
        writer.write_outputs(results, output_dir)
        print(f"Обработано страниц: {results['total_pages']}")
        print(f"Использовано токенов: {results['total_tokens']}")
        print(f"Стоимость: ${results['total_cost_usd']}")


if __name__ == "__main__":
    main()

