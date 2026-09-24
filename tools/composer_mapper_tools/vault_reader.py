from __future__ import annotations

from pathlib import Path


def discover_markdown_files(vault_root: str, relative_glob: str) -> list[Path]:
    root = Path(vault_root)
    return sorted(root.glob(relative_glob))


def read_markdown_file(path: str | Path) -> str:
    return Path(path).read_text()
