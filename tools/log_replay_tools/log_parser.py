from __future__ import annotations

import re
import warnings
from pathlib import Path


def parse_wsbcc_log(log_file_path: str) -> list[dict]:
    """Parse WSBCC log lines into replayable request/response entries."""
    entries = []
    for line_number, line in enumerate(Path(log_file_path).read_text(encoding="utf-8").splitlines(), start=1):
        parsed = _parse_log_line(line, line_number)
        if parsed:
            entries.append(parsed)
        elif line.strip():
            warnings.warn(f"Skipping unparseable WSBCC log line {line_number}", stacklevel=2)
    return entries


def _parse_log_line(line: str, line_number: int) -> dict | None:
    operation = _extract_key(line, "operation_name") or _extract_key(line, "operation")
    channel = _extract_key(line, "channel")
    request_xml = _extract_xml_value(line, "request_xml") or _extract_xml_value(line, "request")
    response_xml = _extract_xml_value(line, "response_xml") or _extract_xml_value(line, "response")
    if not operation or not channel or not request_xml or not response_xml:
        return None
    timestamp = _extract_key(line, "timestamp") or line.split(" ", 1)[0]
    return {
        "timestamp": timestamp,
        "operation_name": operation,
        "channel": channel,
        "request_xml": request_xml,
        "response_xml": response_xml,
        "source_log_ref": f"{Path('log').name}:{line_number}",
    }


def _extract_key(line: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}=([^\s]+)", line)
    return match.group(1) if match else None


def _extract_xml_value(line: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}=(<.+?>)(?=\s+\w+=|$)", line)
    return match.group(1) if match else None
