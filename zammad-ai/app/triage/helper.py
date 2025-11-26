import html
import re


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities from text.

    Args:
        text: Raw HTML string.

    Returns:
        Plain text without tags and with entities unescaped.
    """
    # Remove HTML tags
    clean_text = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities and normalize whitespace
    clean_text = html.unescape(clean_text)
    clean_text = " ".join(clean_text.split())
    return clean_text
