from __future__ import annotations

import re
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_section


def resolve_decorator_chains(format_vault_path: str) -> list[tuple[str, list[str]]]:
    """Read a format vault note and return formatter decorator chains in format order."""
    md_text = Path(format_vault_path).read_text(encoding="utf-8")
    structure = parse_section(md_text, "Structure")
    chains: dict[str, list[str]] = {}
    current_formatter: str | None = None
    for raw_line in structure.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line.startswith("</"):
            continue
        if line.startswith("decorator:"):
            decorator = re.search(r"decorator:\s*<([^\s/>]+)", line)
            if current_formatter and decorator:
                chains.setdefault(current_formatter, []).append(decorator.group(1))
            continue
        formatter = _formatter_identifier(line)
        if formatter:
            current_formatter = formatter
            chains.setdefault(current_formatter, [])
    return [(identifier, decorators) for identifier, decorators in chains.items() if decorators]


def get_decorator_chain_for_field(
    decorator_chains: list[tuple[str, list[str]]],
    field_name: str,
) -> list[str]:
    """Return the decorator chain for a field name, or an empty list when absent."""
    field_prefix = f"{field_name}/"
    for formatter_identifier, decorators in decorator_chains:
        if formatter_identifier.startswith(field_prefix):
            return decorators
    return []


def _formatter_identifier(line: str) -> str | None:
    match = re.search(r"<([^\s/>]+).*?\bdataName=\"([^\"]+)\"", line)
    if not match:
        return None
    return f"{match.group(2)}/{match.group(1)}"
