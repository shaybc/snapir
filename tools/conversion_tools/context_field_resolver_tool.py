from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from models.conversion_models import ContextField, ContextFieldInventory
from tools.composer_mapper_tools.frontmatter_parser import parse_section
from tools.conversion_tools.context_hierarchy_resolver_tool import get_context_hierarchy
from tools.java_analysis_tools.java_source_reader import read_java_source, resolve_source_path
from tools.state_store_tools._json import loads
from tools.state_store_tools.context_field_inventories import (
    get_context_field_inventory,
    upsert_context_field_inventory,
)


class CycleDetectedError(RuntimeError):
    """Raised when context field resolution encounters a cyclic context hierarchy."""


def resolve_context_fields(
    conn: sqlite3.Connection,
    context_id: str,
    channel: str,
    run_id: str,
    composer_root: str,
) -> ContextFieldInventory:
    """Resolve accessible context fields across a pre-built context hierarchy."""
    hierarchy = get_context_hierarchy(conn, context_id, run_id)
    if hierarchy.has_cycle:
        raise CycleDetectedError(f"Context hierarchy has a cycle: {context_id}")
    fields_by_name: dict[str, ContextField] = {}
    for index, level_id in enumerate(hierarchy.chain):
        inherited = index != 0
        for operation in _operations_for_context(conn, run_id, level_id):
            operation_metadata = loads(operation["metadata_json"], {}) or {}
            _collect_formatter_fields(conn, operation_metadata, run_id, level_id, inherited, fields_by_name)
            _collect_implclass_fields(
                conn,
                operation_metadata,
                run_id,
                composer_root,
                level_id,
                inherited,
                fields_by_name,
            )
    inventory = ContextFieldInventory(
        context_id=context_id,
        channel=channel,
        full_chain=hierarchy.chain,
        fields=list(fields_by_name.values()),
    )
    upsert_context_field_inventory(
        conn,
        context_id=context_id,
        channel=channel,
        run_id=run_id,
        full_chain=hierarchy.chain,
        inventory=inventory.model_dump(mode="json"),
        status="ready",
    )
    return inventory


def get_accessible_fields(
    conn: sqlite3.Connection,
    context_id: str,
    run_id: str,
) -> list[ContextField]:
    """Read pre-built accessible context fields for a context."""
    row = conn.execute(
        """
        SELECT * FROM context_field_inventories
        WHERE context_id = ? AND run_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (context_id, run_id),
    ).fetchone()
    if row is None:
        return []
    loaded = get_context_field_inventory(conn, context_id, row["channel"], run_id)
    inventory = loaded.get("inventory_json") if loaded else None
    if not inventory:
        return []
    return [ContextField(**field) for field in inventory.get("fields", [])]


def _operations_for_context(conn: sqlite3.Connection, run_id: str, context_id: str):
    rows = conn.execute(
        "SELECT * FROM source_artifacts WHERE run_id = ? AND kind = 'operation'",
        (run_id,),
    ).fetchall()
    return [
        row for row in rows
        if context_id in str(loads(row["metadata_json"], {}) or {})
    ]


def _collect_formatter_fields(
    conn: sqlite3.Connection,
    operation_metadata: dict,
    run_id: str,
    context_level: str,
    inherited: bool,
    fields_by_name: dict[str, ContextField],
) -> None:
    for format_id in operation_metadata.get("ref_formats", {}).values():
        artifact = _source_artifact(conn, run_id, "format", format_id)
        if artifact is None or not artifact["source_path"]:
            continue
        structure = parse_section(Path(artifact["source_path"]).read_text(encoding="utf-8"), "Structure")
        for tag_name, field_name in _formatter_fields(structure):
            _add_field(
                fields_by_name,
                field_name=field_name,
                context_level=context_level,
                source="formatter",
                inferred_type=_infer_java_type(tag_name),
                inherited=inherited,
                writer=format_id,
            )


def _collect_implclass_fields(
    conn: sqlite3.Connection,
    operation_metadata: dict,
    run_id: str,
    composer_root: str,
    context_level: str,
    inherited: bool,
    fields_by_name: dict[str, ContextField],
) -> None:
    for opstep_id in operation_metadata.get("steps", []):
        opstep = _source_artifact(conn, run_id, "opStep", opstep_id)
        metadata = loads(opstep["metadata_json"], {}) if opstep else {}
        fqcn = metadata.get("impl_class")
        source_path = resolve_source_path(composer_root, fqcn) if fqcn else None
        if source_path is None:
            continue
        source = read_java_source(source_path)
        for field_name in _context_fields(source, ("setValueAt", "setValue")):
            _add_field(
                fields_by_name,
                field_name=field_name,
                context_level=context_level,
                source="implclass",
                inferred_type="String",
                inherited=inherited,
                writer=opstep_id,
            )
        for field_name in _context_fields(source, ("getValueAt", "getValue")):
            _add_field(
                fields_by_name,
                field_name=field_name,
                context_level=context_level,
                source="implclass",
                inferred_type="String",
                inherited=inherited,
                reader=opstep_id,
            )


def _add_field(
    fields_by_name: dict[str, ContextField],
    *,
    field_name: str,
    context_level: str,
    source: str,
    inferred_type: str,
    inherited: bool,
    writer: str | None = None,
    reader: str | None = None,
) -> None:
    if field_name not in fields_by_name:
        fields_by_name[field_name] = ContextField(
            name=field_name,
            context_level=context_level,
            source=source,
            inferred_type=inferred_type,
            inherited=inherited,
            written_by=[],
            read_by=[],
        )
    field = fields_by_name[field_name]
    if writer and writer not in field.written_by:
        field.written_by.append(writer)
    if reader and reader not in field.read_by:
        field.read_by.append(reader)


def _formatter_fields(structure: str) -> list[tuple[str, str]]:
    fields = []
    for match in re.finditer(r"<([^\s/>]+).*?\bdataName=\"([^\"]+)\"", structure):
        fields.append((match.group(1), match.group(2)))
    return fields


def _context_fields(source: str, call_names: tuple[str, ...]) -> list[str]:
    calls = "|".join(re.escape(call_name) for call_name in call_names)
    return sorted(set(re.findall(rf"\.(?:{calls})\s*\(\s*\"([^\"]+)\"", source)))


def _infer_java_type(formatter_tag: str) -> str:
    return {
        "CCDate": "LocalDate",
        "CCBoolean": "boolean",
        "NumberFormat": "BigDecimal",
        "CCIColl": "List<Object>",
    }.get(formatter_tag, "String")


def _source_artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()
