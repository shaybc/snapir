from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from models.conversion_models import (
    ClosureBlockingIssue,
    ClosureStatus,
    DbLookupRequirement,
    FormatSet,
)
from tools.composer_mapper_tools.frontmatter_parser import parse_section
from tools.conversion_tools.decorator_chain_resolver_tool import resolve_decorator_chains
from tools.state_store_tools._json import loads


def resolve_format_dependencies(
    conn: sqlite3.Connection,
    format_ids: list[str],
    run_id: str,
    vault_root: str,
) -> FormatSet:
    """Resolve format dependencies and tag mappings recursively from vault notes."""
    format_set = FormatSet()
    queue = list(format_ids)
    visited: set[str] = set()
    while queue:
        format_id = queue.pop(0)
        if not format_id or format_id in visited:
            continue
        visited.add(format_id)
        artifact = _source_artifact(conn, run_id, "format", format_id)
        if artifact is None:
            format_set.unresolved_format_refs.append(format_id)
            format_set.blocking_issues.append(_issue(ClosureStatus.BLOCKED_MISSING_FORMAT, format_id))
            continue
        format_set.all_format_ids.append(format_id)
        md_text = _read_format_note(artifact, vault_root, format_id)
        structure = parse_section(md_text, "Structure")
        formatter_tags = _formatter_tags(structure)
        format_set.formatter_tags.extend(_new_items(formatter_tags, format_set.formatter_tags))
        for formatter_identifier, decorators in resolve_decorator_chains(_format_note_path(artifact, vault_root, format_id)):
            format_set.decorator_chains[formatter_identifier] = decorators
        metadata = loads(artifact["metadata_json"], {}) or {}
        format_set.transparent_ccxml_nodes.extend(
            _new_items(metadata.get("transparent_ccxml_nodes", []), format_set.transparent_ccxml_nodes)
        )
        format_set.db_lookups.extend(_db_lookups(metadata.get("database_lookups", [])))
        for nested_id in _nested_format_refs(md_text):
            if nested_id not in visited and nested_id not in queue:
                queue.append(nested_id)
        for tag_name in [*formatter_tags, *_decorator_tags(format_set.decorator_chains)]:
            if _tag_exists(conn, tag_name, run_id) is False:
                format_set.blocking_issues.append(_issue(ClosureStatus.BLOCKED_UNKNOWN_TAG, tag_name))
    return format_set


def get_format_blocking_issues(format_set: FormatSet) -> list[ClosureBlockingIssue]:
    """Return resolver issues attached to a FormatSet."""
    return format_set.blocking_issues


def _source_artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()


def _read_format_note(artifact, vault_root: str, format_id: str) -> str:
    return Path(_format_note_path(artifact, vault_root, format_id)).read_text(encoding="utf-8")


def _format_note_path(artifact, vault_root: str, format_id: str) -> str:
    source_path = artifact["source_path"]
    if source_path:
        return str(source_path)
    return str(Path(vault_root) / "formats" / f"{format_id}.md")


def _formatter_tags(structure: str) -> list[str]:
    tags = []
    for raw_line in structure.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line.startswith("</") or line.startswith("decorator:"):
            continue
        match = re.search(r"<([^\s/>]+)", line)
        if match and match.group(1) not in tags:
            tags.append(match.group(1))
    return tags


def _decorator_tags(decorator_chains: dict[str, list]) -> list[str]:
    tags = []
    for decorators in decorator_chains.values():
        for decorator in decorators:
            if decorator not in tags:
                tags.append(decorator)
    return tags


def _nested_format_refs(md_text: str) -> list[str]:
    refs = []
    for match in re.finditer(r"\brefFmt\s*[:=]\s*\"?([A-Za-z0-9_.-]+)\"?", md_text):
        if match.group(1) not in refs:
            refs.append(match.group(1))
    return refs


def _db_lookups(values: list[dict]) -> list[DbLookupRequirement]:
    lookups = []
    for value in values:
        try:
            lookups.append(DbLookupRequirement(**value))
        except Exception:
            continue
    return lookups


def _tag_exists(conn: sqlite3.Connection, tag_name: str, run_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM tag_registry
        WHERE tag_name = ? AND run_id = ?
        LIMIT 1
        """,
        (tag_name, run_id),
    ).fetchone()
    return row is not None


def _issue(kind: ClosureStatus, entity_id: str) -> ClosureBlockingIssue:
    return ClosureBlockingIssue(kind=kind, entity_id=entity_id, detail=kind.value)


def _new_items(values: list, existing: list) -> list:
    return [value for value in values if value not in existing]
