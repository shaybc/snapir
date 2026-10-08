"""Present model failure evidence without credential-bearing diagnostic fields."""

import re
import logging
import sys
import traceback
import os
from urllib.parse import urlsplit, urlunsplit


def sanitize_diagnostic(text: str) -> str:
    """Redact URL credentials, query values, and common authentication fields."""
    for name, value in os.environ.items():
        if value and len(value) >= 8 and any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(value, "[REDACTED]")
    def safe_url(match):
        try:
            url = urlsplit(match.group())
            host = url.netloc.rsplit("@", 1)[-1]
            query = "[REDACTED]" if url.query else ""
            return urlunsplit((url.scheme, host, url.path, query, "[REDACTED]" if url.fragment else ""))
        except ValueError:
            return "[REDACTED URL]"
    text = re.sub(r"https?://[^\s\"'<>]+", safe_url, text, flags=re.IGNORECASE)
    text = re.sub(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", r"\1 [REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"([\"']?(?:cookie|set-cookie|proxy-authorization)[\"']?\s*[:=]\s*)(?:[\"'][^\"'\r\n]*[\"']|[^\r\n]+)", r"\1'[REDACTED]'", text, flags=re.IGNORECASE)
    text = re.sub(r"((?:[\"']?)(?:api[_ -]?key|x-goog-api-key|x-api-key|authorization|access[_ -]?token|refresh[_ -]?token|password|client[_ -]?secret|token)[\"']?\s*[:=]\s*)(?:[\"'][^\"'\r\n]*[\"']|[^\s,;}]+)", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    return text


class SafeDiagnosticFormatter(logging.Formatter):
    """Redact formatted logs, including exception chains, without altering records."""

    def format(self, record) -> str:
        copy = logging.makeLogRecord(record.__dict__.copy())
        return sanitize_diagnostic(super().format(copy))


def print_failure_traceback(error: BaseException) -> None:
    """Print a redacted exception chain and stack to standard error."""
    print(sanitize_diagnostic("".join(traceback.format_exception(error))), file=sys.stderr, end="")
