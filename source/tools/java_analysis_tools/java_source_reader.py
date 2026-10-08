from __future__ import annotations

from pathlib import Path

from constants import MAX_SOURCE_CHARS_PER_CONVERSION


def read_java_source(source_file_path: str) -> str:
    """Read a Java source file from disk with the conversion source-size guard."""
    path = Path(source_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Java source file not found: {source_file_path}")
    source = path.read_text(encoding="utf-8")
    if len(source) > MAX_SOURCE_CHARS_PER_CONVERSION:
        raise ValueError(
            f"Java source file exceeds MAX_SOURCE_CHARS_PER_CONVERSION: {source_file_path}"
        )
    return source


def resolve_source_path(composer_root: str, fqcn: str) -> str | None:
    """Resolve a fully qualified Java class name to a source file under composer_root."""
    if not fqcn.strip():
        return None
    from tools.source_discovery_tools import discover_java_sources, resolve_indexed_source

    return resolve_indexed_source(discover_java_sources(composer_root), fqcn)
