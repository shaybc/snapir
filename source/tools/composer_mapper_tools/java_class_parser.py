from __future__ import annotations

import re

from models.composer_models import ComposerJavaClass
from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_bullet_values,
    parse_frontmatter,
    parse_section,
)


def parse_java_class_note(md_text: str, source_path: str) -> ComposerJavaClass:
    frontmatter = parse_frontmatter(md_text)
    fqcn = str(frontmatter.get("entity_id", ""))
    ibm_imports = _parse_ibm_imports(parse_section(md_text, "IBM Dependency Warning"))
    return ComposerJavaClass(
        fqcn=fqcn,
        simple_name=fqcn.rsplit(".", 1)[-1] if fqcn else "",
        package_name=_first_bullet(parse_section(md_text, "Package")) or fqcn.rsplit(".", 1)[0],
        source_file=str(frontmatter.get("source_file", "")),
        source_hash=str(frontmatter.get("source_hash", "")),
        parent_class=frontmatter.get("parent_class") or None,
        interfaces=list(frontmatter.get("interfaces", [])),
        shared=bool(frontmatter.get("shared", False)),
        used_by_steps=list(frontmatter.get("used_by_steps", [])),
        behavior_types=parse_bullet_values(parse_section(md_text, "Behavior Type")),
        return_codes=_parse_return_codes(parse_section(md_text, "Return Codes")),
        setter_names=parse_bullet_values(parse_section(md_text, "Setter Methods")),
        has_ibm_dependency=bool(ibm_imports) or bool(parse_section(md_text, "IBM Dependency Warning")),
        ibm_imports=ibm_imports,
        inferred_external_dependencies=parse_bullet_values(
            parse_section(md_text, "Inferred External Dependencies")
        ),
        conversion_status=str(frontmatter.get("conversion_status", "not_started")),
    )


def _parse_return_codes(section: str) -> dict[str, list[str]]:
    codes: dict[str, list[str]] = {}
    for value in parse_bullet_values(section):
        match = re.search(r"Returns\s+(\S+)(?:\s+\((.*)\))?", value)
        if match:
            meanings = []
            if match.group(2):
                meanings = [item.strip() for item in match.group(2).split(";") if item.strip()]
            codes[match.group(1)] = meanings
    return codes


def _parse_ibm_imports(section: str) -> list[str]:
    return [
        value
        for value in parse_bullet_values(section)
        if value.startswith("com.ibm") or value == "com.ibm"
    ]


def _first_bullet(section: str) -> str | None:
    values = parse_bullet_values(section)
    return clean_markdown_value(values[0]) if values else None
