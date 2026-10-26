from __future__ import annotations

import re
from pathlib import Path


def validate_channel_in_registry(vault_root: str, target_channels: list[str]) -> list[str]:
    from tools.workspace_intake_tools.vault_validator import validate_vault_input
    return validate_vault_input(vault_root, target_channels)[1]


def _extract_channels(content: str) -> set[str]:
    channels: set[str] = set()
    for line in content.splitlines():
        channels.update(re.findall(r"\b[A-Z][A-Z0-9_]{1,}\b", line))
    return channels
