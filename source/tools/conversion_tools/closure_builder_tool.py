from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

from models.conversion_models import (
    ClosureBlockingIssue,
    ClosureStatus,
    FormatSet,
    OperationClosure,
)
from tools.conversion_tools.channel_filter_tool import filter_opsteps_for_channel
from tools.conversion_tools.closure_validator_tool import validate_closure
from tools.conversion_tools.context_field_resolver_tool import get_accessible_fields
from tools.conversion_tools.context_hierarchy_resolver_tool import get_context_hierarchy
from tools.conversion_tools.format_dependency_resolver_tool import (
    get_format_blocking_issues,
    resolve_format_dependencies,
)
from tools.conversion_tools.java_impl_resolver_tool import resolve_java_impls
from tools.state_store_tools._json import loads
from tools.state_store_tools.operation_closures import upsert_operation_closure


LOGGER = logging.getLogger(__name__)


def build_operation_closure(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
    composer_root: str,
    vault_root: str,
    classpath_index=None,
    profile=None,
) -> OperationClosure:
    """Build, validate, and store a deterministic operation closure."""
    from tools.composer_mapper_tools.scoped_vault_importer import require_qualified_conversion
    require_qualified_conversion(conn, run_id)
    operation = _required_artifact(conn, run_id, "operation", operation_id)
    metadata = loads(operation["metadata_json"], {}) or {}
    external_records = []
    rules = profile.external_dependencies if profile else []
    document = profile.composer_behavior_document if profile else None
    included_opsteps, excluded_opsteps = filter_opsteps_for_channel(conn, operation_id, channel, run_id)
    from tools.conversion_tools.operation_call_closure import resolve_operation_calls
    operation_calls, operation_call_issues = resolve_operation_calls(conn, run_id, operation_id, channel, included_opsteps, profile)
    java_classes, java_issues = resolve_java_impls(conn, included_opsteps, run_id, composer_root, classpath_index,
                                                rules, document, external_records)
    formats = resolve_format_dependencies(conn, list(metadata.get("ref_formats", {}).values()), run_id, vault_root)
    format_issues = get_format_blocking_issues(formats)
    context_id = metadata.get("operation_context") or ""
    context_chain, context_issues = _context_chain(conn, context_id, run_id)
    context_fields = get_accessible_fields(conn, context_id, run_id) if context_id else []
    routing_graph = _routing_graph(conn, included_opsteps, run_id)
    return_body_switches = _return_body_switches(conn, included_opsteps, run_id)
    if "csErrorReplyFormat" in metadata.get("ref_formats", {}):
        formats.error_reply_format_id = metadata["ref_formats"]["csErrorReplyFormat"]
    formats.request_format_id = metadata.get("ref_formats", {}).get("csRequestFormat")
    formats.reply_format_id = metadata.get("ref_formats", {}).get("csReplyFormat")
    closure = OperationClosure(
        operation_id=operation_id,
        channel=channel,
        run_id=run_id,
        status=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
        blocking_issues=[*java_issues, *format_issues, *context_issues, *operation_call_issues],
        source_xml_path=metadata.get("source_file", ""),
        operation_fields=metadata.get("operation_fields"),
        ini_values=list(metadata.get("ini_values", [])),
        host_key=metadata.get("host_key"),
        ref_formats=dict(metadata.get("ref_formats", {})),
        return_body_switches=return_body_switches,
        included_opstep_ids=included_opsteps,
        operation_calls=operation_calls,
        excluded_opsteps=excluded_opsteps,
        routing_graph=routing_graph,
        java_classes=java_classes,
        formats=formats,
        context_id=context_id,
        context_chain=context_chain,
        context_fields=context_fields,
        shared_formats=_shared_artifacts(conn, run_id, "format", formats.all_format_ids),
        shared_java_classes=[ref.fqcn for ref in java_classes if ref.shared],
        source_hash_composite=_source_hash_composite(conn, run_id, operation_id, included_opsteps, formats.all_format_ids),
    )
    closure = closure.model_copy(update={"external_dependencies": external_records})
    closure = validate_closure(closure, conn, run_id, composer_root)
    from tools.source_discovery_tools import discover_java_sources
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from tools.state_store_tools.component_inventory import get_conversion_inventory
    from tools.conversion_tools.conversion_component_set import resolve_conversion_components
    from tools.conversion_tools.java_dependency_readiness import check_java_dependencies

    source_index = discover_java_sources(composer_root)
    classpath_index = classpath_index or discover_java_classpath(composer_root)
    components, dependency_issues = resolve_conversion_components(conn, closure, composer_root, source_index,
        rules, document, external_records,
        service_classpath=classpath_index if profile and profile.conversion_strategy == 'behavior_units' else None)
    implementations, _, _ = get_conversion_inventory(conn, run_id, operation_id, channel)
    expected_hashes = {str((Path(composer_root) / item['source_path']).resolve()): item['source_hash']
                       for item in implementations.values()}
    components, java_issues = check_java_dependencies(components, source_index, classpath_index, expected_hashes,
        rules, document, external_records)
    dependency_issues.extend(java_issues)
    dependency_issues.extend(ClosureBlockingIssue(kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
        entity_id=operation_id, detail=issue) for issue in classpath_index.issues)
    from runtime.composer_behavior_context import compact_behavior_evidence
    external_records, behavior_evidence = compact_behavior_evidence(external_records)
    closure = closure.model_copy(update={'conversion_components': components,
        'conversion_components_checked': True, 'external_dependencies': external_records,
        'composer_behavior_evidence': behavior_evidence,
        'blocking_issues': [*closure.blocking_issues, *dependency_issues],
        'source_hash_composite': hashlib.sha256((closure.source_hash_composite + str(sorted(
            (item.kind, item.logical_id, item.source_hash) for item in components))).encode()).hexdigest()})
    closure = validate_closure(closure, conn, run_id, composer_root)
    upsert_operation_closure(
        conn,
        operation_id=operation_id,
        channel=channel,
        run_id=run_id,
        status=closure.status.value,
        closure=closure.model_dump(mode="json"),
        blocking_issues=[issue.model_dump(mode="json") for issue in closure.blocking_issues],
        source_hash_composite=closure.source_hash_composite,
    )
    return closure


def build_closures_for_batch(
    conn: sqlite3.Connection,
    operation_ids: list[str],
    channel: str,
    run_id: str,
    composer_root: str,
    vault_root: str,
) -> list[OperationClosure]:
    """Build operation closures for a batch and log ready/blocked counts."""
    closures = [
        build_operation_closure(conn, operation_id, channel, run_id, composer_root, vault_root)
        for operation_id in operation_ids
    ]
    ready_count = sum(1 for closure in closures if closure.status == ClosureStatus.READY)
    blocked = [closure for closure in closures if closure.status != ClosureStatus.READY]
    breakdown: dict[str, int] = {}
    for closure in blocked:
        breakdown[closure.status.value] = breakdown.get(closure.status.value, 0) + 1
    LOGGER.info("Closure batch complete: READY=%s BLOCKED=%s %s", ready_count, len(blocked), breakdown)
    return closures


def _context_chain(
    conn: sqlite3.Connection,
    context_id: str,
    run_id: str,
) -> tuple[list[str], list[ClosureBlockingIssue]]:
    if not context_id:
        return [], [ClosureBlockingIssue(
            kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
            entity_id="context",
            detail="Operation context is missing",
        )]
    try:
        hierarchy = get_context_hierarchy(conn, context_id, run_id)
    except Exception as exc:
        return [], [ClosureBlockingIssue(
            kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
            entity_id=context_id,
            detail=str(exc),
        )]
    if hierarchy.has_cycle:
        return hierarchy.chain, [ClosureBlockingIssue(
            kind=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
            entity_id=context_id,
            detail="Context hierarchy has a cycle",
        )]
    return hierarchy.chain, []


def _routing_graph(conn: sqlite3.Connection, opstep_ids: list[str], run_id: str) -> dict[str, dict]:
    graph = {}
    included = set(opstep_ids)
    for opstep_id in opstep_ids:
        opstep = _required_artifact(conn, run_id, "opStep", opstep_id)
        metadata = loads(opstep["metadata_json"], {}) or {}
        transitions = dict(metadata.get("transitions", {}))
        graph[opstep_id] = {
            key: target
            for key, target in transitions.items()
            if target in included or str(target).lower() in {"end", "next"}
        }
    return graph


def _return_body_switches(conn: sqlite3.Connection, opstep_ids: list[str], run_id: str) -> dict[str, str]:
    switches = {}
    for opstep_id in opstep_ids:
        opstep = _required_artifact(conn, run_id, "opStep", opstep_id)
        metadata = loads(opstep["metadata_json"], {}) or {}
        switches.update(metadata.get("return_body_switches", {}))
    return switches


def _shared_artifacts(conn: sqlite3.Connection, run_id: str, kind: str, logical_ids: list[str]) -> list[str]:
    shared = []
    for logical_id in logical_ids:
        artifact = _artifact(conn, run_id, kind, logical_id)
        if artifact is not None and artifact["shared"]:
            shared.append(logical_id)
    return shared


def _source_hash_composite(
    conn: sqlite3.Connection,
    run_id: str,
    operation_id: str,
    opstep_ids: list[str],
    format_ids: list[str],
) -> str:
    hashes = []
    for kind, logical_id in [("operation", operation_id)]:
        artifact = _artifact(conn, run_id, kind, logical_id)
        if artifact and artifact["source_hash"]:
            hashes.append(artifact["source_hash"])
    for kind, ids in (("opStep", opstep_ids), ("format", format_ids)):
        for logical_id in ids:
            artifact = _artifact(conn, run_id, kind, logical_id)
            if artifact and artifact["source_hash"]:
                hashes.append(artifact["source_hash"])
    return hashlib.sha256("".join(sorted(hashes)).encode("utf-8")).hexdigest()


def _required_artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    artifact = _artifact(conn, run_id, kind, logical_id)
    if artifact is None:
        raise KeyError(f"{kind} source artifact not found: {logical_id}")
    return artifact


def _artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()
