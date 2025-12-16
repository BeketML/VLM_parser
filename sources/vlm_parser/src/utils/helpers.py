import base64
import re


def encode_image_to_b64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
    return base64.b64encode(image_bytes).decode("ascii")


def strip_current_page_tags(text: str) -> str:
    """
    Remove <current_page> and </current_page> tags from text, preserving inner content.
    """
    if not text:
        return text
    # Remove exact tags; keep content between them
    cleaned = re.sub(r"</?current_page>", "", text)
    return cleaned.strip()

