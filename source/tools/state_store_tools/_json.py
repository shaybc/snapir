from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def load_json_columns(row: Any, columns: tuple[str, ...]) -> dict[str, Any] | None:
    data = row_to_dict(row)
    if data is None:
        return None
    for column in columns:
        data[column] = loads(data.get(column), [] if column.endswith("_json") else None)
    return data


def placeholders(values: list[str]) -> str:
    return ", ".join("?" for _ in values)
