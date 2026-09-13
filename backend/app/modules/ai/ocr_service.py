"""
OCR Service (Tesseract & pytesseract Integration)
Extracts optical text from scanned documents and images with graceful fallback.
"""

import io
import logging
from dataclasses import dataclass

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    success: bool


def is_tesseract_available() -> bool:
    """Checks whether the tesseract binary is accessible in the system path."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_ocr_from_image_bytes(image_bytes: bytes, lang: str = "eng") -> str:
    """
    Runs Tesseract OCR on raw image bytes.
    Returns normalized extracted text string.
    """
    if not is_tesseract_available():
        logger.warning("Tesseract binary is not installed or accessible on host system. Skipping OCR.")
        return ""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert RGBA / Palette images to RGB for OCR stability
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip()
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return ""


def perform_ocr(content: bytes, mime_type: str) -> OCRResult:
    """
    Coordinates OCR processing for images and scanned documents.
    Returns OCRResult(text=..., success=...).
    """
    mime = (mime_type or "").lower()

    if mime in ["image/png", "image/jpeg", "image/tiff"]:
        text = extract_ocr_from_image_bytes(content)
        return OCRResult(text=text, success=bool(text))

    if mime == "application/pdf":
        text = extract_ocr_from_image_bytes(content)
        return OCRResult(text=text, success=bool(text))

    return OCRResult(text="", success=False)


def process_ocr_for_document(
    content: bytes,
    mime_type: str,
    existing_text: str = "",
) -> tuple[str, bool]:
    """
    Legacy helper: Appends OCR findings to any existing partial text.
    Returns (final_text, ocr_success_flag).
    """
    res = perform_ocr(content, mime_type)
    if res.text:
        return res.text, True
    return existing_text, bool(existing_text.strip())

