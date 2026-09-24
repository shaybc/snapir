from __future__ import annotations

from pathlib import Path


REQUIRED_VAULT_PATHS = [
    "analysis",
    "analysis/channel-operation-registry.md",
]


def validate_vault_structure(vault_root: str) -> list[str]:
    root = Path(vault_root)
    missing: list[str] = []
    if not root.exists():
        return [vault_root]
    for relative_path in REQUIRED_VAULT_PATHS:
        path = root / relative_path
        if not path.exists():
            missing.append(str(path))
    return missing
