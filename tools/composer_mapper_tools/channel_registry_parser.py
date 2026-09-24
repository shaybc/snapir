from __future__ import annotations

from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import clean_markdown_value


def parse_channel_operation_registry(registry_md_path: str) -> list[tuple[str, str, str]]:
    path = Path(registry_md_path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped or "Operation" in stripped:
            continue
        cells = [clean_markdown_value(cell.strip()) for cell in stripped.strip("|").split("|")]
        if len(cells) >= 3:
            rows.append((cells[0], cells[1], cells[2]))
    return rows
