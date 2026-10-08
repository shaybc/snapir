from __future__ import annotations

from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_section,
)


def parse_channel_note(md_text: str, channel: str) -> list[tuple[str, str, str]]:
    section = parse_section(md_text, "Tag Mappings") or parse_section(md_text, "Tag Mapping Summary")
    mappings = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        value = clean_markdown_value(stripped[2:])
        if "->" in value:
            tag_name, fqcn = value.split("->", 1)
        elif ":" in value:
            tag_name, fqcn = value.split(":", 1)
        else:
            continue
        mappings.append((tag_name.strip(), fqcn.strip(), channel))
    return mappings
