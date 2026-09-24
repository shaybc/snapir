from __future__ import annotations

import re
from typing import Any


def parse_frontmatter(md_text: str) -> dict[str, Any]:
    match = re.search(r"(?s)(?:^|\n)---\n(.*?)\n---(?:\n|$)", md_text)
    if match is None:
        return {}
    return _parse_yaml_subset(match.group(1))


def parse_section(md_text: str, section_heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(section_heading)}\s*\n(.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(md_text)
    if match is None:
        return ""
    return match.group(1).strip()


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if current_key and line.startswith("  - "):
            result[current_key].append(_coerce_scalar(line[4:].strip()))
            continue
        current_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            result[key] = []
        elif value == "":
            result[key] = []
            current_key = key
        else:
            result[key] = _coerce_scalar(value)
    return result


def _coerce_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def clean_markdown_value(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("`", "")
    return value.strip()


def parse_bullet_values(section_text: str) -> list[str]:
    values = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            value = clean_markdown_value(stripped[2:])
            if value and value.lower() != "none":
                values.append(value)
    return values


def parse_key_value_bullets(section_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in parse_bullet_values(section_text):
        if ":" in item:
            key, value = item.split(":", 1)
            values[key.strip()] = value.strip()
        elif "->" in item:
            key, value = item.split("->", 1)
            values[key.strip()] = value.strip()
    return values
