"""
Structured Security & Audit Logging
Provides JSON formatted logs with correlation IDs and sensitive data redaction.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variable for correlating log entries per request
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# Sensitive patterns that must be sanitized before emission
SENSITIVE_KEYS = {
    "password", "secret", "token", "access_token", "refresh_token",
    "jwt", "api_key", "authorization", "cookie", "private_key",
    "signature", "secret_key"
}

PASSWORD_PATTERN = re.compile(r'("?(?:password|token|secret)"?\s*[:=]\s*)"?([^",\s]+)"?', re.IGNORECASE)


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON with security redaction."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if present in request context
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id

        # Attach any custom extra fields
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            for k, v in record.extra_fields.items():
                if k.lower() in SENSITIVE_KEYS:
                    log_data[k] = "[REDACTED]"
                else:
                    log_data[k] = v

        # Redact any sensitive substrings in the message
        serialized = json.dumps(log_data)
        serialized = PASSWORD_PATTERN.sub(r'\1"[REDACTED]"', serialized)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            serialized = json.dumps(log_data)

        return serialized


def setup_logging(level: str = "INFO") -> None:
    """Configures root logger with JSON formatting and stdout handler."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Silence verbose 3rd party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger instance."""
    return logging.getLogger(name)
