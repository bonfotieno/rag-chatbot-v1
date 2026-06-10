"""Recursive character text splitter for chunking long documents."""
from typing import List
from ...config import settings


# Separator hierarchy: paragraph → sentence → word → character
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _split_with_separator(text: str, separator: str) -> List[str]:
    """Split text by separator and put the separator back at the end of each part."""
    if separator == "":
        return list(text)
    parts = text.split(separator)
    # Re-attach separator to every part except the last (best-effort sentence preservation)
    result = []
    for i, part in enumerate(parts):
        if part:
            if i < len(parts) - 1 and separator not in ("\n\n", "\n"):
                result.append(part + separator)
            else:
                result.append(part)
    return result


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[str]:
    """Split *text* into overlapping chunks using a recursive character strategy.

    Args:
        text: The cleaned document text to chunk.
        chunk_size: Maximum characters per chunk (defaults to settings.CHUNK_SIZE).
        chunk_overlap: Character overlap between consecutive chunks
                       (defaults to settings.CHUNK_OVERLAP).

    Returns:
        List of non-empty chunk strings.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    if not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    chunks: List[str] = []
    _recursive_split(text, _SEPARATORS, chunk_size, chunk_overlap, chunks)
    return [c.strip() for c in chunks if c.strip()]


def _recursive_split(
    text: str,
    separators: List[str],
    chunk_size: int,
    chunk_overlap: int,
    output: List[str],
) -> None:
    """Recursively split text using the separator hierarchy."""
    if len(text) <= chunk_size:
        output.append(text)
        return

    # Pick the first separator that actually appears in the text
    separator = separators[-1]  # fallback: split character-by-character
    new_separators = []
    for i, sep in enumerate(separators):
        if sep == "" or sep in text:
            separator = sep
            new_separators = separators[i + 1:]
            break

    splits = _split_with_separator(text, separator)

    # Merge splits into chunks that respect chunk_size
    current_chunk: List[str] = []
    current_len = 0

    for split in splits:
        split_len = len(split)

        if current_len + split_len > chunk_size and current_chunk:
            # Emit the current chunk
            chunk_text_str = separator.join(current_chunk) if separator else "".join(current_chunk)
            if len(chunk_text_str) > chunk_size and new_separators:
                # Still too large — recurse with finer separators
                _recursive_split(chunk_text_str, new_separators, chunk_size, chunk_overlap, output)
            else:
                output.append(chunk_text_str)

            # Build overlap: keep the tail of the current chunk
            overlap_len = 0
            overlap_parts: List[str] = []
            for part in reversed(current_chunk):
                if overlap_len + len(part) > chunk_overlap:
                    break
                overlap_parts.insert(0, part)
                overlap_len += len(part)

            current_chunk = overlap_parts
            current_len = overlap_len

        current_chunk.append(split)
        current_len += split_len

    # Emit the last chunk
    if current_chunk:
        chunk_text_str = separator.join(current_chunk) if separator else "".join(current_chunk)
        if len(chunk_text_str) > chunk_size and new_separators:
            _recursive_split(chunk_text_str, new_separators, chunk_size, chunk_overlap, output)
        else:
            output.append(chunk_text_str)
