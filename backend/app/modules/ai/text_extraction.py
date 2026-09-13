"""
Multi-Format Text Extraction Service
Extracts text from PDF, DOCX, XLSX, images, and plaintext with normalization.
Detects when scanned documents require OCR processing.
"""

import io
import re

import docx
import openpyxl
from pypdf import PdfReader


def normalize_text(text: str) -> str:
    """Cleans up raw extracted text: strips nulls, normalizes whitespace and line wraps."""
    if not text:
        return ""
    # Strip null characters
    text = text.replace("\x00", "")
    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on lines
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def extract_pdf_text(file_bytes: bytes) -> tuple[str, int]:
    """
    Extracts text and page count from PDF binary content using pypdf.
    Returns (extracted_text, page_count).
    """
    stream = io.BytesIO(file_bytes)
    reader = PdfReader(stream)
    page_count = len(reader.pages)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    return "\n\n".join(text_parts), page_count


def extract_docx_text(file_bytes: bytes) -> str:
    """Extracts paragraphs and tables from DOCX binary content."""
    stream = io.BytesIO(file_bytes)
    doc = docx.Document(stream)
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


def extract_xlsx_text(file_bytes: bytes) -> str:
    """Extracts cell contents from Excel workbook."""
    stream = io.BytesIO(file_bytes)
    wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"--- Sheet: {sheet.title} ---")
        for row in sheet.iter_rows(values_only=True):
            row_vals = [str(val).strip() for val in row if val is not None]
            if row_vals:
                parts.append(" | ".join(row_vals))
    return "\n".join(parts)


def extract_text_from_bytes(
    content: bytes,
    mime_type: str,
    filename: str = "",
) -> tuple[str, bool]:
    """
    Primary text extraction gateway.
    Returns tuple of (extracted_text, needs_ocr).
    """
    mime = (mime_type or "").lower()
    fname = (filename or "").lower()

    # Direct Images always need OCR
    if mime in ["image/png", "image/jpeg", "image/tiff"] or fname.endswith((".png", ".jpg", ".jpeg", ".tiff")):
        return "", True

    # PDF Processing
    if mime == "application/pdf" or fname.endswith(".pdf"):
        try:
            raw_text, page_count = extract_pdf_text(content)
            clean_text = normalize_text(raw_text)
            # If page count > 0 and extracted text is sparse (< 80 chars per page), it's a scanned PDF
            if page_count > 0 and len(clean_text) < (80 * page_count):
                return clean_text, True
            return clean_text, False
        except Exception:
            # If pypdf fails to parse, route to OCR
            return "", True

    # DOCX Processing
    if (
        mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or fname.endswith(".docx")
    ):
        try:
            text = extract_docx_text(content)
            return normalize_text(text), False
        except Exception:
            return "", False

    # XLSX Processing
    if (
        mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        or fname.endswith(".xlsx")
    ):
        try:
            text = extract_xlsx_text(content)
            return normalize_text(text), False
        except Exception:
            return "", False

    # Plaintext fallback
    try:
        decoded = content.decode("utf-8", errors="replace")
        return normalize_text(decoded), False
    except Exception:
        return "", False


def extract_document_text(
    file_bytes: bytes,
    filename: str = "",
    mime_type: str = "",
) -> tuple[str, bool]:
    """
    Standard interface for extracting document text and checking if OCR is needed.
    Returns (extracted_text, is_scanned_or_needs_ocr).
    """
    return extract_text_from_bytes(content=file_bytes, mime_type=mime_type, filename=filename)

