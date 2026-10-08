from __future__ import annotations

import re

from models.composer_models import ComposerFormat
from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_bullet_values,
    parse_frontmatter,
    parse_section,
)


def parse_format_note(md_text: str, source_path: str) -> ComposerFormat:
    frontmatter = parse_frontmatter(md_text)
    structure = parse_section(md_text, "Structure")
    decorator_chains = _parse_decorator_chains(structure)
    return ComposerFormat(
        id=str(frontmatter.get("entity_id", "")),
        source_file=str(frontmatter.get("source_file", "")),
        source_hash=str(frontmatter.get("source_hash", "")),
        shared=bool(frontmatter.get("shared", False)),
        used_by_operations=list(frontmatter.get("used_by_operations", [])),
        has_serialization_flags=bool(parse_bullet_values(parse_section(md_text, "Serialization Notes"))),
        serialization_flags=parse_bullet_values(parse_section(md_text, "Serialization Notes")),
        database_lookups=_parse_database_lookups(parse_section(md_text, "Database Lookups")),
        decorator_chains=decorator_chains,
        transparent_ccxml_nodes=_parse_transparent_ccxml_nodes(structure),
        inferred_external_dependencies=parse_bullet_values(
            parse_section(md_text, "Inferred External Dependencies")
        ),
        conversion_status=str(frontmatter.get("conversion_status", "not_started")),
    )


def _parse_decorator_chains(structure: str) -> dict[str, list[str]]:
    chains: dict[str, list[str]] = {}
    current_formatter: str | None = None
    for raw_line in structure.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line.startswith("</"):
            continue
        if line.startswith("decorator:"):
            if current_formatter:
                decorator = re.search(r"decorator:\s*<([^\s/>]+)", line)
                if decorator:
                    chains.setdefault(current_formatter, []).append(decorator.group(1))
            continue
        formatter = re.search(r"<([^\s/>]+)", line)
        if formatter:
            current_formatter = _formatter_node_id(formatter.group(1), line)
            chains.setdefault(current_formatter, [])
    return {key: value for key, value in chains.items() if value}


def _formatter_node_id(tag_name: str, line: str) -> str:
    data_name = re.search(r'dataName="([^"]+)"', line)
    if data_name:
        return f"{data_name.group(1)}/{tag_name}"
    return tag_name


def _parse_transparent_ccxml_nodes(structure: str) -> list[str]:
    nodes = []
    for raw_line in structure.splitlines():
        line = raw_line.strip()
        if line.startswith("<CCXML"):
            data_name = re.search(r'dataName="([^"]+)"', line)
            nodes.append(data_name.group(1) if data_name else "CCXML")
    return nodes


def _parse_database_lookups(section: str) -> list[dict]:
    lookups = []
    for value in parse_bullet_values(section):
        if ":" not in value:
            continue
        field_name, details = value.split(":", 1)
        lookup = {"field_name": field_name.strip()}
        for part in details.split(","):
            if " " not in part.strip():
                continue
            key, val = part.strip().split(" ", 1)
            normalized_key = {
                "fromTable": "from_table",
                "fromColumn": "from_column",
                "keyValue": "key_value_field",
            }.get(key)
            if normalized_key:
                lookup[normalized_key] = clean_markdown_value(val)
        lookups.append(lookup)
    return lookups
