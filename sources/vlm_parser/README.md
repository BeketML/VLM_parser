## VLM Parser

Vision-Language Model (VLM) PDF parser that converts PDF pages to images and extracts full, clean text per page using an LLM with image understanding. The parser enforces strict separation between previous-slide context and current-slide output to avoid mixing content across pages.

### Key features
- Per-page parsing with cross-slide awareness: previous slide is provided as XML-tagged context, current page text is extracted strictly without copying previous content
- Deterministic output shape for app consumption (Markdown per page and a summary JSON)
- Usage and cost tracking per run

### Project layout
- `vlm_parser/main.py`: CLI entry point (`python -m vlm_parser.main`)
- `vlm_parser/config.py`: environment/config (model name, API key loader)
- `vlm_parser/src/prompts.py`: prompt and context instructions
- `vlm_parser/src/analyzer.py`: single-image call to the VLM with context and output parsing
- `vlm_parser/src/extractor.py`: end-to-end PDF → images → VLM → `.md` files and JSON
- `vlm_parser/src/utils/`:
  - `client.py`: OpenAI client factory
  - `helpers.py`: utility helpers (image → base64)
  - `pricing.py`: token pricing table and cost calculator

### Requirements
- Python 3.10+
- `OPENAI_API_KEY` in environment (e.g., in `.env`)

### Install
Use the project’s existing virtualenv and requirements (at repository root):
```bash
pip install -r requirements.txt
```

### Run
Run from the repository root to keep package imports valid:
```bash
python -m vlm_parser.main --pdf C:\path\to\file.pdf --out results_dir
```

Artifacts:
- `results_dir/images/*.png`: rendered pages
- `results_dir/md/<n>.md`: the text of page n only (no previous content)
- `results_dir/<pdf_basename>.json`: run summary with usage and total cost

### Prompt engineering and context design
- Previous page text is provided to the model as XML block: `<previous_text>…</previous_text>`
- The prompt instructs the model to output only current page text inside a dedicated block `<current_page>…</current_page>`; the analyzer extracts only this block, with fallback to JSON or raw text when necessary
- The context rules emphasize: continue tables/lists without duplication, do not copy any content from previous, preserve reading order, keep completeness

### JSON output schema (summary)
Example (fields may be extended):
```json
{
  "pdf_path": "C:\\path\\file.pdf",
  "total_pages": 18,
  "results_dir": "C:\\path\\results_dir",
  "images_dir": "C:\\path\\results_dir\\images",
  "md_dir": "C:\\path\\results_dir\\md",
  "model": "gpt-4.1-mini",
  "total_prompt_tokens": 12345,
  "total_completion_tokens": 6789,
  "total_cost_usd": 1.234567,
  "slides": [
    {
      "slide_num": 1,
      "image_path": ".../images/file_page_1.png",
      "title": "...",
      "content": "...",  
      "usage": {"prompt_tokens": 700, "completion_tokens": 300, "total_tokens": 1000}
    }
  ]
}
```

### How cost is calculated
The calculator lives in `vlm_parser/src/utils/pricing.py`.

- Pricing table (USD per 1K tokens): `MODEL_PRICES_USD_PER_1K_TOKENS`
- For each run we sum model-reported tokens across pages:
  - `total_input_tokens` = sum of `prompt_tokens`
  - `total_output_tokens` = sum of `completion_tokens`
- Cost formula:
  - `input_cost = (total_input_tokens / 1000) * prices["input"]`
  - `output_cost = (total_output_tokens / 1000) * prices["output"]`
  - `total_cost_usd = round(input_cost + output_cost, 6)`

Notes:
- Cached input pricing exists in the table for some models (`cached_input`) but is not currently applied; the extractor uses only `input` and `output` prices
- Ensure the `model` name in `config.py` (`MODEL_NAME`) exists in the pricing map

### Programmatic usage
```python
from vlm_parser.src.extractor import extract_slides_vlm

slides = extract_slides_vlm(
    pdf_path=r"C:\\path\\file.pdf",
    results_dir=r"C:\\path\\results_dir",
)
```

### Troubleshooting
- ImportError (attempted relative import): run from repo root with `python -m vlm_parser.main ...`
- Empty `.md` files: verify `OPENAI_API_KEY` and that the image renders for the page
- Cost is zero: model name not found in pricing map; add it to `pricing.py`


