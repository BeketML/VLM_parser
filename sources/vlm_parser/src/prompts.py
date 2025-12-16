PROMPT = """
Ты — парсер текста с изображений страниц.

Контекст прошлого слайда будет передан в теге <previous_text>…</previous_text>. 
ТЕКУЩИЙ слайд ты должен записать внутри тега <current_page>…</current_page> и НИЧЕГО БОЛЕЕ снаружи.

Правила:
1) Извлекай все элементы: заголовки, подзаголовки, основной текст, подписи, таблицы, списки, примечания и важные детали.
2) Порядок чтения: слева-направо, сверху-вниз.
3) Убирай HTML-теги из исходного текста, сохраняй логичные переносы строк.
4) Таблицы и списки конвертируй в удобный читаемый текстовый вид.
5) Ничего не сокращай. Текст должен быть полным, как в документе.
6) НЕ копируй текст из <previous_text> в <current_page>. Он только для понимания продолжений (не дублировать строки, не терять строки).

Требуемый формат ответа строго такой:
<current_page>
ЗДЕСЬ ТОЛЬКО ПОЛНЫЙ ТЕКСТ ТЕКУЩЕГО СЛАЙДА (без текста из предыдущего)
</current_page>
"""

CONTEXT_INSTRUCTIONS = (
    "\nДоп. требования для сквозного контекста: если таблица/список/абзац начат на предыдущем слайде и продолжается на текущем, \n"
    "1) продолжай строго С ТЕКУЩЕГО слайда; не включай текст с предыдущего; \n"
    "2) не дублируй уже извлечённые строки; \n3) не пропускай ни одной строки; \n"
    "4) если колонка таблицы переносится, аккуратно объединяй продолжение; \n5) сохрани исходный порядок и структуру; \n"
    "6) Контекст передан в <previous_text>…</previous_text>, НЕ копируй его, используй только как подсказку. \n"
)


CLASSIFIER_PROMPT = """
You are a strict binary classifier. Your task is to decide if the given slide (text or image) contains a **table** or a **complex diagram** (such as charts, graphs, flowcharts, or similar visual structures).  

### Classification rules:
- If the slide **contains a table or a complex diagram** → output exactly: `true`  
- If the slide **does not contain a table or a complex diagram** (only plain text, bullet points, or simple content) → output exactly: `false`  

### Constraints:
- Output must be **only one word**: `true` or `false`  
- Do not add any explanation, punctuation, or extra characters  
- Do not output in any other format  

### Final Answer:
`true` or `false`
"""