"""Text cleaning utilities."""
import re


def clean_text(text: str) -> str:
    """Clean extracted text for chunking and embedding.

    Steps:
    1. Normalise line endings.
    2. Collapse runs of whitespace within lines.
    3. Collapse more than two consecutive blank lines into two.
    4. Strip leading/trailing whitespace.
    """
    if not text:
        return ""

    # Normalise Windows/Mac line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove null bytes and other control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)

    # Collapse whitespace within each line (preserve intentional indentation partially)
    lines = []
    for line in text.split("\n"):
        # Replace multiple spaces/tabs with a single space
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned_line)

    text = "\n".join(lines)

    # Collapse more than 2 consecutive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
