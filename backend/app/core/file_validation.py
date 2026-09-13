"""
File Security & Magic-Byte Validation Engine
Validates MIME types, magic bytes, filenames, and file sizes to prevent spoofing and traversal attacks.
"""

import io
import os
import re
import zipfile
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationException

# Explicitly supported legal document MIME types
ALLOWED_MIME_TYPES = set(settings.ALLOWED_DOCUMENT_MIME_TYPES)

# Known dangerous executable and script magic byte headers
DISALLOWED_SIGNATURES = [
    (b"MZ", "Windows PE executable (EXE/DLL)"),
    (b"\x7fELF", "Linux ELF executable"),
    (b"PK\x05\x06", "Empty or suspicious ZIP archive"),
    (b"#!/", "Shell script"),
    (b"<?php", "PHP script"),
    (b"<script", "HTML/JavaScript payload"),
    (b"%!PS", "PostScript payload"),
]


def sanitize_filename(raw_filename: str) -> str:
    """
    Sanitizes raw user-supplied filename to prevent directory traversal,
    null byte injection, and special character exploits.
    Preserves a clean, human-readable name.
    """
    if not raw_filename or not raw_filename.strip():
        raise ValidationException(
            detail="Filename cannot be empty",
            error_code="FILE_001",
        )

    # 1. Reject null bytes and path traversal patterns
    if "\x00" in raw_filename:
        raise ValidationException(
            detail="Filename contains prohibited null bytes",
            error_code="FILE_002",
        )
    if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise ValidationException(
            detail="Filename contains prohibited path traversal sequences",
            error_code="FILE_003",
        )

    # 2. Extract basename only
    base = os.path.basename(raw_filename).strip()

    # 3. Replace unsafe characters (keep alphanumerics, hyphens, underscores, dots)
    clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", base)

    # 4. Collapse multiple dots or underscores
    clean_name = re.sub(r"\.{2,}", ".", clean_name)
    clean_name = re.sub(r"_{2,}", "_", clean_name)

    # 5. Enforce length boundary (max 200 chars to allow room)
    name_stem = Path(clean_name).stem[:180]
    ext = Path(clean_name).suffix[:20].lower()
    if not ext:
        raise ValidationException(
            detail="File must possess a valid file extension",
            error_code="FILE_004",
        )

    sanitized = f"{name_stem}{ext}"
    return sanitized


def validate_file_size(size_bytes: int, max_bytes: int = settings.MAX_UPLOAD_SIZE_BYTES) -> None:
    """Validates that uploaded file size is within acceptable non-zero boundaries."""
    if size_bytes <= 0:
        raise ValidationException(
            detail="Uploaded file is empty (0 bytes)",
            error_code="FILE_005",
        )
    if size_bytes > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        raise ValidationException(
            detail=f"File size exceeds maximum allowed threshold of {max_mb}MB (received {actual_mb:.2f}MB)",
            error_code="FILE_006",
        )


def validate_file_content(
    content: bytes,
    claimed_mime: str | None,
    filename: str,
) -> str:
    """
    Validates file integrity, magic bytes, and checks for dangerous signatures.
    Returns verified canonical MIME type.
    """
    if len(content) < 4:
        raise ValidationException(
            detail="File content is corrupted or too small to evaluate",
            error_code="FILE_007",
        )

    # 1. Check for known dangerous executable/script signatures
    sample_header = content[:32]
    for sig, desc in DISALLOWED_SIGNATURES:
        if sample_header.startswith(sig) or sig in content[:1024]:
            raise ValidationException(
                detail=f"Uploaded file matches prohibited executable/script signature: {desc}",
                error_code="FILE_008",
            )

    ext = Path(filename).suffix.lower()

    # 2. Match signature by file type
    # PDF
    if content.startswith(b"%PDF-") or (b"%PDF" in content[:1024]):
        canonical_mime = "application/pdf"
        if ext not in (".pdf",):
            raise ValidationException(
                detail=f"File signature identifies PDF content but filename extension is '{ext}'",
                error_code="FILE_009",
            )
        return canonical_mime

    # PNG
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        canonical_mime = "image/png"
        if ext not in (".png",):
            raise ValidationException(
                detail=f"File signature identifies PNG content but extension is '{ext}'",
                error_code="FILE_009",
            )
        return canonical_mime

    # JPEG
    if content.startswith(b"\xff\xd8\xff"):
        canonical_mime = "image/jpeg"
        if ext not in (".jpg", ".jpeg"):
            raise ValidationException(
                detail=f"File signature identifies JPEG content but extension is '{ext}'",
                error_code="FILE_009",
            )
        return canonical_mime

    # Office OpenXML (DOCX, XLSX)
    if content.startswith(b"PK\x03\x04"):
        # Validate that it is a genuine Office OpenXML zip archive
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                namelist = z.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise ValidationException(
                        detail="ZIP archive does not conform to genuine Office OpenXML specifications",
                        error_code="FILE_010",
                    )
                if ext in (".docx",) and any(n.startswith("word/") for n in namelist):
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif ext in (".xlsx",) and any(n.startswith("xl/") for n in namelist):
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                else:
                    raise ValidationException(
                        detail=f"Archive structure does not match expected format for extension '{ext}'",
                        error_code="FILE_010",
                    )
        except zipfile.BadZipFile as e:
            raise ValidationException(
                detail="Corrupted Office document archive",
                error_code="FILE_010",
            ) from e

    raise ValidationException(
        detail="Unsupported file format or unrecognized magic bytes. Supported formats: PDF, DOCX, XLSX, JPEG, PNG",
        error_code="FILE_011",
    )
