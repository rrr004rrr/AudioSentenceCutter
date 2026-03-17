import re


def clean_filename(text: str, max_length: int = 50) -> str:
    if not text or not text.strip():
        return "unnamed"
    # Remove illegal filename characters (Windows + Unix)
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    # Remove leading/trailing dots and spaces
    cleaned = cleaned.strip('. ')
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned[:max_length].strip()
    return cleaned or "unnamed"
