from __future__ import annotations

import re
from pathlib import Path


def validate_channel_in_registry(vault_root: str, target_channels: list[str]) -> list[str]:
    registry_path = Path(vault_root) / "analysis" / "channel-operation-registry.md"
    if not registry_path.exists():
        return list(target_channels)
    content = registry_path.read_text()
    available = _extract_channels(content)
    return [channel for channel in target_channels if channel not in available]


def _extract_channels(content: str) -> set[str]:
    channels: set[str] = set()
    for line in content.splitlines():
        channels.update(re.findall(r"\b[A-Z][A-Z0-9_]{1,}\b", line))
    return channels
