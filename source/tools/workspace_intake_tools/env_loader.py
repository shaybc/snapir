from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from runtime.project_paths import project_root
from typing import Any

import constants


LIST_KEYS = {
    "TARGET_CHANNELS",
    "TARGET_LANGUAGES",
    "INCLUDE_OPERATIONS",
    "EXCLUDE_OPERATIONS",
    "FORBIDDEN_DEPENDENCIES",
    "CLASSPATH_JARS",
    "APPROVED_MAVEN_REPOSITORY_URLS",
    "ALLOWED_IBM_ARTIFACTS",
    "ALLOWED_IBM_CLASSES",
}


def load_env_with_fallbacks(env_file: str | None = None) -> dict[str, Any]:
    env_values = _read_env_file(env_file)
    resolved: dict[str, Any] = {}
    for key in _constant_keys():
        value = deepcopy(env_values.get(key, getattr(constants, key)))
        if key in LIST_KEYS:
            value = _parse_list(value)
        elif isinstance(getattr(constants, key), dict) and isinstance(value, str):
            value = json.loads(value)
        elif isinstance(getattr(constants, key), bool):
            value = _parse_bool(value)
        elif isinstance(getattr(constants, key), int):
            value = int(value)
        base = Path(env_file or ".env").resolve().parent if key in env_values else project_root()
        if key in {"COMPOSER_ROOT", "VAULT_ROOT", "OUTPUT_ROOT", "NATIVE_JAVA_ROOT", "TEMPLATES_ROOT", "GOLDEN_TESTS_ROOT", "DB_PATH", "COMPOSER_MAPPER_JAR", "MAVEN_SETTINGS_PATH", "MAVEN_LOCAL_REPOSITORY", "DEPLOYMENT_TEMPLATE_DIR"} and value:
            value = str((base / value).resolve())
        elif key == "CLASSPATH_JARS":
            value = [str((base / path).resolve()) for path in value]
        elif key == "ECLIPSE_CLASSPATH_VARIABLES":
            value = {name: str((base / path).resolve()) for name, path in value.items()}
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
        if key.isupper() and not key.startswith("_") and key != "SUPPORTED_TARGET_LANGUAGES"
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
