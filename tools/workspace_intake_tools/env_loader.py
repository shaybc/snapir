from __future__ import annotations

from pathlib import Path
from typing import Any

import constants


LIST_KEYS = {
    "TARGET_CHANNELS",
    "TARGET_LANGUAGES",
    "INCLUDE_OPERATIONS",
    "EXCLUDE_OPERATIONS",
    "FORBIDDEN_DEPENDENCIES",
}


def load_env_with_fallbacks(env_file: str | None = None) -> dict[str, Any]:
    env_values = _read_env_file(env_file)
    resolved: dict[str, Any] = {}
    for key in _constant_keys():
        value = env_values.get(key, getattr(constants, key))
        if key in LIST_KEYS:
            value = _parse_list(value)
        elif isinstance(getattr(constants, key), bool):
            value = _parse_bool(value)
        elif isinstance(getattr(constants, key), int):
            value = int(value)
        resolved[key] = value
    if resolved["INCLUDE_OPERATIONS"] == []:
        resolved["INCLUDE_OPERATIONS"] = None
    if resolved["EXCLUDE_OPERATIONS"] == []:
        resolved["EXCLUDE_OPERATIONS"] = None
    return resolved


def _constant_keys() -> list[str]:
    return [
        key
        for key in dir(constants)
        if key.isupper() and not key.startswith("_")
    ]


def _read_env_file(env_file: str | None) -> dict[str, str]:
    if env_file is None:
        path = Path(".env")
        if not path.exists():
            return {}
    else:
        path = Path(env_file)
        if not path.exists():
            return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _parse_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    return items


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
