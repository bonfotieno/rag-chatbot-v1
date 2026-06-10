"""Text extraction from various document formats."""
import io
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


def extract_from_pdf(file_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """Extract text from a PDF.

    Returns:
        (full_text, pages) where pages is a list of (page_number, page_text) tuples.
    """
    import fitz  # PyMuPDF

    pages: List[Tuple[int, str]] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        pages.append((page_num + 1, text))
    doc.close()

    full_text = "\n".join(text for _, text in pages)
    return full_text, pages


def extract_from_docx(file_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """Extract text from a DOCX file.

    Returns:
        (full_text, pages) — DOCX has no native page concept; all text is page 1.
    """
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    full_text = "\n".join(paragraphs)
    return full_text, [(1, full_text)]


def extract_from_txt(file_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """Extract text from a plain-text file."""
    text = file_bytes.decode("utf-8", errors="replace")
    return text, [(1, text)]


def extract_from_csv(file_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """Convert a CSV to a textual representation."""
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    text = df.to_string(index=False)
    return text, [(1, text)]


def extract_from_xlsx(file_bytes: bytes) -> Tuple[str, List[Tuple[int, str]]]:
    """Convert an XLSX workbook to a textual representation (one section per sheet)."""
    import pandas as pd

    xl = pd.ExcelFile(io.BytesIO(file_bytes))
    parts: List[str] = []
    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name)
        parts.append(f"=== Sheet: {sheet_name} ===\n{df.to_string(index=False)}")
    text = "\n\n".join(parts)
    return text, [(1, text)]


def extract_text(file_bytes: bytes, file_type: str) -> Tuple[str, List[Tuple[int, str]]]:
    """Dispatch text extraction based on file_type (lowercase extension without dot)."""
    file_type = file_type.lower().lstrip(".")

    extractors = {
        "pdf": extract_from_pdf,
        "docx": extract_from_docx,
        "doc": extract_from_docx,
        "txt": extract_from_txt,
        "csv": extract_from_csv,
        "xlsx": extract_from_xlsx,
        "xls": extract_from_xlsx,
    }

    extractor = extractors.get(file_type)
    if extractor is None:
        raise ValueError(f"Unsupported file type: {file_type}")

    logger.info("Extracting text from %s file (%d bytes)", file_type, len(file_bytes))
    return extractor(file_bytes)
