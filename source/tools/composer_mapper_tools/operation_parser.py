from __future__ import annotations

from models.composer_models import ComposerOperation
from tools.composer_mapper_tools.frontmatter_parser import (
    clean_markdown_value,
    parse_bullet_values,
    parse_frontmatter,
    parse_key_value_bullets,
    parse_section,
)


def parse_operation_note(md_text: str, source_path: str) -> ComposerOperation:
    frontmatter = parse_frontmatter(md_text)
    ref_formats = {}
    request = _first_bullet(parse_section(md_text, "Request Format"))
    reply = _first_bullet(parse_section(md_text, "Reply Format"))
    if request:
        ref_formats["csRequestFormat"] = request
    if reply:
        ref_formats["csReplyFormat"] = reply
    ref_formats.update(parse_key_value_bullets(parse_section(md_text, "Other Formats")))

    operation_attrs = parse_key_value_bullets(parse_section(md_text, "Operation Attributes"))
    context = _first_bullet(parse_section(md_text, "Context"))
    if context and context.lower().startswith("unresolved:"):
        context = context.split(":", 1)[1].strip()

    return ComposerOperation(
        id=str(frontmatter.get("entity_id", "")),
        channel=str(frontmatter.get("channel", "")),
        source_file=str(frontmatter.get("source_file", "")),
        source_hash=str(frontmatter.get("source_hash", "")),
        operation_context=context,
        host_key=frontmatter.get("host_key"),
        operation_fields=operation_attrs.get("operationFields"),
        write_to_log=operation_attrs.get("writeToLog"),
        write_to_ofec_stat=operation_attrs.get("writeToOfecStat"),
        is_selective_journalising=operation_attrs.get("isSelectiveJournalising"),
        ini_values=parse_bullet_values(parse_section(md_text, "Initial Values (iniValue)")),
        steps=[_strip_step_suffix(step) for step in parse_bullet_values(parse_section(md_text, "Steps"))],
        ref_formats=ref_formats,
        inline_format_ids=[
            value.removeprefix("inline:").strip()
            for value in parse_bullet_values(parse_section(md_text, "Other Formats"))
            if value.startswith("inline:")
        ],
        conversion_status=str(frontmatter.get("conversion_status", "not_started")),
    )


def _first_bullet(section_text: str) -> str | None:
    values = parse_bullet_values(section_text)
    return values[0] if values else None


def _strip_step_suffix(value: str) -> str:
    return clean_markdown_value(value.split(" *(", 1)[0])
