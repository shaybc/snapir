from __future__ import annotations

import re

from models.composer_models import ComposerOpStep
from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_frontmatter,
    parse_key_value_bullets,
    parse_section,
)


def parse_opstep_note(md_text: str, source_path: str) -> ComposerOpStep:
    frontmatter = parse_frontmatter(md_text)
    implementation = _parse_impl_class(parse_section(md_text, "Implementation"))
    return ComposerOpStep(
        id=str(frontmatter.get("entity_id", "")),
        parent_operation_id=_first(frontmatter.get("used_by_operations", [])) or "",
        impl_class=implementation,
        source_file=str(frontmatter.get("source_file", "")),
        source_hash=str(frontmatter.get("source_hash", "")),
        only_for=frontmatter.get("onlyFor"),
        transitions=_parse_transitions(parse_section(md_text, "Transitions")),
        return_body_switches=_parse_return_body_switches(
            parse_section(md_text, "Return Body Switches")
        ),
        parameters=parse_key_value_bullets(parse_section(md_text, "Parameters")),
        conversion_status=str(frontmatter.get("conversion_status", "not_started")),
    )


def _parse_impl_class(section: str) -> str | None:
    for line in section.splitlines():
        if line.strip().startswith("- "):
            value = clean_markdown_value(line.strip()[2:])
            if value.lower() == "unresolved":
                return None
            if value.lower().startswith("unresolved:"):
                return value.split(":", 1)[1].strip()
            return value
    return None


def _parse_transitions(section: str) -> dict[str, str]:
    transitions: dict[str, str] = {}
    for line in section.splitlines():
        value = clean_markdown_value(line.strip().removeprefix("- "))
        if " -> " in value:
            key, target = value.split(" -> ", 1)
            transitions[key.strip()] = target.removeprefix("unresolved ").strip()
    return transitions


def _parse_return_body_switches(section: str) -> dict[str, str]:
    switches: dict[str, str] = {}
    for line in section.splitlines():
        if not line.strip().startswith("- "):
            continue
        value = clean_markdown_value(line.strip()[2:])
        match = re.search(r"RC\s+(\S+)\s+->\s+switch reply body to\s+(.+)", value)
        if match:
            switches[match.group(1)] = match.group(2).strip()
    return switches


def _first(value: object) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return None
