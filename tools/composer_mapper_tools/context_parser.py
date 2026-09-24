from __future__ import annotations

from models.composer_models import ComposerContext
from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_frontmatter,
    parse_key_value_bullets,
    parse_section,
)


def parse_context_note(md_text: str, source_path: str) -> ComposerContext:
    frontmatter = parse_frontmatter(md_text)
    details = parse_key_value_bullets(parse_section(md_text, "Details"))
    parent = details.get("parent")
    if parent and parent.lower() in {"none", "nil", "null"}:
        parent = None
    return ComposerContext(
        id=str(frontmatter.get("entity_id", "")),
        parent_id=clean_markdown_value(parent) if parent else None,
        type=details.get("type", ""),
        source_file=str(frontmatter.get("source_file", "")),
        source_hash=str(frontmatter.get("source_hash", "")),
        used_by_operations=list(frontmatter.get("used_by_operations", [])),
        conversion_status=str(frontmatter.get("conversion_status", "not_started")),
    )
