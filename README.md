# VLM Parser

Парсер PDF-документов с автоматическим выбором оптимального метода обработки. Использует PyMuPDF для простых текстовых страниц и Vision-Language Model (AWS Bedrock + Claude) для сложных страниц с таблицами, диаграммами и изображениями.

## Содержание

- [Установка](#установка)
- [Настройка AWS Bedrock](#настройка-aws-bedrock)
- [User Guide](#user-guide)
  - [Быстрый старт](#быстрый-старт)
  - [CLI команды](#cli-команды)
  - [Программное использование](#программное-использование)
- [Как работает парсер](#как-работает-парсер)
- [Формат выходных данных](#формат-выходных-данных)
- [Настройка параметров](#настройка-параметров)
- [Отладка и логирование](#отладка-и-логирование)

## Установка

### 1. Клонирование репозитория

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd VLM_parser
```

### 2. Создание виртуального окружения

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## Настройка AWS Bedrock

Проект использует AWS Bedrock с моделью Anthropic Claude для обработки сложных страниц.

### Требования

1. **AWS учетные данные** должны быть настроены одним из способов:
   - Переменные окружения: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - AWS credentials file (`~/.aws/credentials`)
   - IAM роль (если запускается на EC2/Lambda)

2. **Регион и модель** настраиваются в `config/settings.py`:
   - `REGION = "eu-central-1"` (по умолчанию)
   - `MODEL_NAME = "eu.anthropic.claude-sonnet-4-20250514-v1:0"` (по умолчанию)

3. **Опционально**: создайте файл `.env` в корне проекта:
```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=eu-central-1
```

## User Guide

### Быстрый старт

Самый простой способ начать работу:

```bash
python main.py parse "путь/к/файлу.pdf" --output "результаты"
```

Это обработает PDF файл и сохранит результаты в указанную директорию.

### CLI команды

Основная точка входа - `main.py`, который использует CLI интерфейс из `src/cli/main.py`.

#### Базовый синтаксис

```bash
python main.py parse <путь> [--output <директория>] [--page <номер>]
```

#### Параметры

- `path` (обязательный) - путь к PDF файлу или директории с PDF файлами
- `--output, -o` - директория для выходных файлов (по умолчанию: `./output`)
- `--page` - номер страницы для выборочного парсинга (1-based индекс)

#### Примеры использования

**Обработка одного PDF файла:**
```bash
python main.py parse "data/pdfs/test1.pdf" --output "data/outputs/test1"
```

**Обработка только одной страницы:**
```bash
python main.py parse "data/pdfs/test1.pdf" --output "data/outputs/test1_page5" --page 5
```

**Обработка всех PDF в директории:**
```bash
python main.py parse "data/pdfs" --output "data/outputs"
```

**Обработка с выводом в текущую директорию:**
```bash
python main.py parse "document.pdf" -o "."
```

### Программное использование

Вы можете использовать парсер как Python библиотеку:

```python
from src.processors.pdf_processor import PDFProcessor
from src.output.writers import OutputWriter

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
    
    # Вывод метрик
    print(f"Обработано страниц: {results['total_pages']}")
    print(f"Использовано токенов: {results['total_tokens']}")
    print(f"Стоимость: ${results['total_cost_usd']}")
    print(f"Время обработки: {results['total_time_sec']} сек")
```

#### Обработка директории программно

```python
processor = PDFProcessor()
processor.process_directory(
    dir_path="data/pdfs",
    output_base_dir="data/outputs"
)
```

#### Обработка конкретной страницы

```python
results = processor.process(
    pdf_path="document.pdf",
    output_dir="./output",
    page_index=3  # Обработать только 3-ю страницу
)
```

## Как работает парсер

Парсер автоматически выбирает оптимальный метод обработки для каждой страницы:

### 1. Анализ страницы

Для каждой страницы выполняется анализ (`src/utils/page_analyzer.py`):
- Извлечение текста через PyMuPDF
- Подсчет длины текста (`text_length`)
- Проверка наличия изображений (`has_images`)
- Вычисление плотности текста (`text_density`)
- Определение признаков:
  - `has_almost_no_text` - текста меньше порога (по умолчанию 100 символов)
  - `is_image_based` - мало текста, но есть изображения

### 2. Классификация через VLM

Для страниц с достаточным количеством текста (не `has_almost_no_text` и не `is_image_based`) выполняется классификация через VLM:
- Страница рендерится в изображение
- Изображение отправляется в AWS Bedrock с запросом определить наличие таблиц/диаграмм
- Результат: `has_table_or_diagram` (boolean) и метрики использования токенов

### 3. Выбор парсера

Логика выбора (`select_parser` в `src/processors/pdf_processor.py`):

- **VLM парсер** используется если:
  - Страница имеет почти нет текста (`has_almost_no_text`)
  - Страница является image-based (`is_image_based`)
  - Классификатор определил наличие таблиц/диаграмм (`has_tables`)

- **PyMuPDF парсер** используется для обычных текстовых страниц без таблиц

### 4. Извлечение текста

В зависимости от выбранного парсера:
- **PyMuPDF**: быстрое извлечение текста напрямую из PDF
- **VLM**: отправка изображения страницы в Bedrock для извлечения текста (включая таблицы и диаграммы)

## Формат выходных данных

После обработки в выходной директории создается следующая структура:

```
output_dir/
├── metrics.json          # Метрики обработки
├── output.md             # Объединенный текст всех страниц
└── pages/
    ├── 1.md             # Текст 1-й страницы
    ├── 2.md             # Текст 2-й страницы
    └── ...
```

### Структура metrics.json

```json
{
  "file": "test.pdf",
  "total_pages": 5,
  "total_tokens": 13645,
  "total_time_sec": 58.21,
  "total_cost_usd": 0.077427,
  "pages": [
    {
      "page": 1,
      "parser": "vlm",
      "tokens": 2115,
      "classifier_tokens": 0,
      "parser_tokens": 2115,
      "time_sec": 5.93
    }
  ]
}
```

**Поля метрик:**

- `file` - имя обработанного PDF файла
- `total_pages` - общее количество обработанных страниц
- `total_tokens` - суммарное количество использованных токенов (классификация + извлечение)
- `total_time_sec` - общее время обработки в секундах
- `total_cost_usd` - примерная стоимость обработки в USD (рассчитывается по ценам из `config/settings.py`)
- `pages` - массив метрик по каждой странице:
  - `page` - номер страницы (1-based)
  - `parser` - использованный парсер (`pymupdf` или `vlm`)
  - `tokens` - общее количество токенов для страницы
  - `classifier_tokens` - токены, потраченные на классификацию (0 если классификация не выполнялась)
  - `parser_tokens` - токены, потраченные на извлечение текста
  - `time_sec` - время обработки страницы в секундах

## Настройка параметров

Основные настройки находятся в `config/settings.py`:

### Пороги и лимиты

- `MIN_TEXT_LENGTH = 100` - минимальная длина текста для определения "почти нет текста"
- `DEFAULT_DPI = 200` - DPI для рендеринга страниц в изображения
- `REQUEST_DELAY = 0.2` - задержка между запросами к Bedrock (секунды)

### AWS настройки

- `REGION = "eu-central-1"` - AWS регион
- `MODEL_NAME` - идентификатор модели Bedrock

### Retry настройки

- `MAX_RETRIES = 5` - максимальное количество попыток при ошибках
- `BASE_DELAY = 1.0` - базовая задержка для экспоненциального backoff

### Цены на модели

Цены для расчета стоимости находятся в `MODEL_PRICES_USD_PER_1K_TOKENS`. Можно добавить свои модели или обновить цены.

## Отладка и логирование

### Уровни логирования

Логирование настраивается в `src/cli/main.py`. По умолчанию используется уровень `INFO`.

**Что логируется:**

- Информация о начале обработки каждой страницы
- Результаты анализа страницы
- Запуск/пропуск классификации с причинами
- Выбор парсера для каждой страницы
- Ошибки при обращении к Bedrock
- Предупреждения при проблемах с парсингом

**Пример логов:**

```
2025-01-XX XX:XX:XX - INFO - Обработка PDF: data/pdfs/test.pdf
2025-01-XX XX:XX:XX - INFO - Обработка страницы 1/5
2025-01-XX XX:XX:XX - INFO - Страница 1: запуск классификации (text_length=1250, is_image_based=False, has_images=False)
2025-01-XX XX:XX:XX - INFO - Страница 1: классификация завершена, has_tables=False, tokens=450
2025-01-XX XX:XX:XX - INFO - Страница 1: выбран парсер pymupdf
```

### Изменение уровня логирования

Для более детальной диагностики можно изменить уровень на `DEBUG` в `src/cli/main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Изменить с INFO на DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Структура проекта

```
VLM_parser/
├── main.py                 # Точка входа CLI
├── requirements.txt         # Зависимости Python
├── config/                  # Конфигурация
│   ├── settings.py         # Настройки проекта
│   └── prompts.py          # Промпты для VLM моделей
├── src/
│   ├── cli/                # CLI интерфейс
│   ├── handlers/           # Обработчики (retry логика)
│   ├── llm/                # Клиент AWS Bedrock
│   ├── output/             # Генерация выходных файлов
│   ├── parsers/            # Парсеры (PyMuPDF, VLM)
│   ├── processors/         # Основная логика обработки
│   └── utils/              # Утилиты (анализ страниц, расчет стоимости)
├── data/                   # Данные (PDF файлы и результаты)
└── examples/               # Примеры использования
```

## Troubleshooting

### Ошибка: ModuleNotFoundError

Убедитесь, что виртуальное окружение активировано и все зависимости установлены:
```bash
pip install -r requirements.txt
```

### Ошибка: AWS credentials not found

Проверьте настройку AWS credentials:
- Переменные окружения `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY`
- Или файл `~/.aws/credentials`
- Или IAM роль (если запускается на AWS)

### Ошибка: ThrottlingException

Bedrock может ограничивать количество запросов. Парсер автоматически использует экспоненциальный backoff для retry. Можно увеличить `REQUEST_DELAY` в `config/settings.py`.

### Классификация не выполняется (classifier_tokens = 0)

Это нормально, если страницы имеют мало текста (`has_almost_no_text`) или являются image-based. Классификация выполняется только для страниц с достаточным количеством текста. Проверьте логи для деталей.

## Быстрый запуск из терминала

### 1. Активировать виртуальное окружение

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate### 2. Запустить парсер через CLI

# Один PDF целиком
python main.py parse "data/pdfs/test1.pdf" --output "data/outputs/test1"

# Только одну страницу (например, 3-ю)
python main.py parse "data/pdfs/test1.pdf" --output "data/outputs/test1_page3" --page 3

# Все PDF в директории
python main.py parse "data/pdfs" --output "data/outputs"### 3. Запуск примера кода (Python)

python examples/basic_usage.pyЭтого блока достаточно, чтобы пользователь сразу понял, как запустить код.

