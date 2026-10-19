from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from models.common_models import RunConfig
from models.composer_models import ComposerContext, ComposerFormat, ComposerJavaClass, ComposerOperation, ComposerOpStep
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
from tools.composer_mapper_tools.channel_registry_parser import parse_channel_operation_registry
from tools.composer_mapper_tools.context_parser import parse_context_note
from tools.composer_mapper_tools.format_parser import parse_format_note
from tools.composer_mapper_tools.java_class_parser import parse_java_class_note
from tools.composer_mapper_tools.operation_parser import parse_operation_note
from tools.composer_mapper_tools.opstep_parser import parse_opstep_note
from tools.composer_mapper_tools.vault_reader import discover_markdown_files, read_markdown_file
from tools.state_store_tools.channel_operations import upsert_channel_operation, upsert_operation
from tools.state_store_tools.source_artifacts import upsert_source_artifact
from tools.state_store_tools.tag_registry import upsert_tag


@dataclass
class VaultImportSummary:
    operations: int = 0
    opsteps: int = 0
    formats: int = 0
    contexts: int = 0
    java_classes: int = 0
    channel_operations: int = 0
    tag_mappings: int = 0
    unresolved_references: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def import_vault(
    conn: sqlite3.Connection,
    vault_root: str,
    run_config: RunConfig,
) -> VaultImportSummary:
    summary = VaultImportSummary()
    root = Path(vault_root)

    for operation_name, channel, xml_file_path in parse_channel_operation_registry(
        str(root / "analysis" / "channel-operation-registry.md")
    ):
        upsert_channel_operation(
            conn,
            operation_name=operation_name,
            channel=channel,
            xml_file_path=xml_file_path,
            run_id=run_config.run_id,
        )
        summary.channel_operations += 1

    for path in discover_markdown_files(vault_root, "channels/*.md"):
        channel = path.stem
        try:
            for tag_name, fqcn, parsed_channel in parse_channel_note(read_markdown_file(path), channel):
                upsert_tag(
                    conn,
                    tag_name=tag_name,
                    fqcn=fqcn,
                    channel=parsed_channel,
                    run_id=run_config.run_id,
                    source_dse_ini=str(path),
                )
                summary.tag_mappings += 1
        except Exception as exc:
            summary.errors.append(f"{path}: {exc}")

    summary.operations += _import_notes(
        conn,
        vault_root,
        "operations/*.md",
        parse_operation_note,
        _store_operation,
        run_config.run_id,
        summary.errors,
    )
    summary.opsteps += _import_notes(
        conn,
        vault_root,
        "opsteps/*.md",
        parse_opstep_note,
        _store_opstep,
        run_config.run_id,
        summary.errors,
    )
    summary.formats += _import_notes(
        conn,
        vault_root,
        "formats/*.md",
        parse_format_note,
        _store_format,
        run_config.run_id,
        summary.errors,
    )
    summary.contexts += _import_notes(
        conn,
        vault_root,
        "contexts/*.md",
        parse_context_note,
        _store_context,
        run_config.run_id,
        summary.errors,
    )
    summary.java_classes += _import_notes(
        conn,
        vault_root,
        "classes/**/*.md",
        parse_java_class_note,
        _store_java_class,
        run_config.run_id,
        summary.errors,
    )

    _populate_operations_table(conn, run_config)
    from tools.operation_call_tools.discovery import discover_operation_calls
    from tools.state_store_tools.operation_calls import save_graph, plan_contracts
    graph = discover_operation_calls(vault_root)
    save_graph(conn, run_config.run_id, graph)
    plan_contracts(conn, run_config.run_id, graph, vault_root)
    summary.unresolved_references.extend(issue['operation'] + ': ' + issue['detail'] for issue in graph['issues'])
    return summary


def _import_notes(conn, vault_root, glob, parser, storer, run_id, errors) -> int:
    count = 0
    for path in discover_markdown_files(vault_root, glob):
        try:
            entity = parser(read_markdown_file(path), str(path))
            storer(conn, entity, str(path), run_id)
            count += 1
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    return count


def _store_operation(conn: sqlite3.Connection, entity: ComposerOperation, path: str, run_id: str) -> None:
    upsert_source_artifact(
        conn,
        artifact_id=f"{run_id}:operation:{entity.id}",
        run_id=run_id,
        kind="operation",
        logical_id=entity.id,
        source_path=path,
        source_hash=entity.source_hash,
        channel=entity.channel,
        shared=False,
        used_by_ids=[entity.id],
        metadata=entity.model_dump(mode="json"),
        conversion_status=entity.conversion_status,
    )


def _store_opstep(conn: sqlite3.Connection, entity: ComposerOpStep, path: str, run_id: str) -> None:
    upsert_source_artifact(
        conn,
        artifact_id=f"{run_id}:opStep:{entity.id}",
        run_id=run_id,
        kind="opStep",
        logical_id=entity.id,
        source_path=path,
        source_hash=entity.source_hash,
        shared=False,
        used_by_ids=[entity.parent_operation_id] if entity.parent_operation_id else [],
        metadata=entity.model_dump(mode="json"),
        conversion_status=entity.conversion_status,
    )


def _store_format(conn: sqlite3.Connection, entity: ComposerFormat, path: str, run_id: str) -> None:
    upsert_source_artifact(
        conn,
        artifact_id=f"{run_id}:format:{entity.id}",
        run_id=run_id,
        kind="format",
        logical_id=entity.id,
        source_path=path,
        source_hash=entity.source_hash,
        shared=entity.shared,
        used_by_ids=entity.used_by_operations,
        metadata=entity.model_dump(mode="json"),
        conversion_status=entity.conversion_status,
    )


def _store_context(conn: sqlite3.Connection, entity: ComposerContext, path: str, run_id: str) -> None:
    upsert_source_artifact(
        conn,
        artifact_id=f"{run_id}:context:{entity.id}",
        run_id=run_id,
        kind="context",
        logical_id=entity.id,
        source_path=path,
        source_hash=entity.source_hash,
        shared=len(entity.used_by_operations) > 1,
        used_by_ids=entity.used_by_operations,
        metadata=entity.model_dump(mode="json"),
        conversion_status=entity.conversion_status,
    )


def _store_java_class(conn: sqlite3.Connection, entity: ComposerJavaClass, path: str, run_id: str) -> None:
    upsert_source_artifact(
        conn,
        artifact_id=f"{run_id}:java_class:{entity.fqcn}",
        run_id=run_id,
        kind="java_class",
        logical_id=entity.fqcn,
        source_path=path,
        source_hash=entity.source_hash,
        shared=entity.shared,
        used_by_ids=entity.used_by_steps,
        metadata=entity.model_dump(mode="json"),
        conversion_status=entity.conversion_status,
    )


def _populate_operations_table(conn: sqlite3.Connection, run_config: RunConfig) -> None:
    channels = run_config.target_channels
    if run_config.run_mode.value == "full_inventory":
        rows = conn.execute(
            "SELECT * FROM channel_operations WHERE run_id = ?", (run_config.run_id,)
        ).fetchall()
    else:
        if not channels:
            return
        placeholders = ", ".join("?" for _ in channels)
        rows = conn.execute(
            f"""
            SELECT * FROM channel_operations
            WHERE run_id = ? AND channel IN ({placeholders})
            """,
            [run_config.run_id, *channels],
        ).fetchall()

    include = set(run_config.include_operations or [])
    exclude = set(run_config.exclude_operations or [])
    for row in rows:
        operation_name = row["operation_name"]
        if include and operation_name not in include:
            continue
        if operation_name in exclude:
            continue
        upsert_operation(
            conn,
            operation_id=operation_name,
            channel=row["channel"],
            run_id=run_config.run_id,
            xml_file_path=row["xml_file_path"],
        )
