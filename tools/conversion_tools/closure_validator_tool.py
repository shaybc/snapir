from __future__ import annotations

import sqlite3
from pathlib import Path

from models.conversion_models import ClosureBlockingIssue, ClosureStatus, OperationClosure


class ClosureNotReadyError(RuntimeError):
    """Raised when conversion is requested for a non-ready operation closure."""


SEVERITY = [
    ClosureStatus.BLOCKED_MISSING_IMPL_CLASS,
    ClosureStatus.BLOCKED_MISSING_FORMAT,
    ClosureStatus.BLOCKED_UNKNOWN_TAG,
    ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
    ClosureStatus.NEEDS_HUMAN_MAPPING,
]


def validate_closure(
    closure: OperationClosure,
    conn: sqlite3.Connection,
    run_id: str,
    composer_root: str,
) -> OperationClosure:
    """Run the deterministic ten-check closure gate."""
    issues = list(closure.blocking_issues)
    issues.extend(_check_impl_refs(closure))
    issues.extend(_check_java_source_files(closure))
    issues.extend(_check_formats_exist(closure, conn, run_id))
    issues.extend(_check_tags_exist(closure, conn, run_id))
    issues.extend(_check_context_chain(closure))
    issues.extend(_check_error_reply_format(closure))
    issues.extend(_check_unresolved_formats(closure))
    issues.extend(_check_routing_covers_return_codes(closure))
    status = _most_severe_status(issues)
    return closure.model_copy(update={"status": status, "blocking_issues": issues})


def assert_closure_ready(closure: OperationClosure) -> None:
    """Stop conversion unless an operation closure passed all deterministic checks."""
    if closure.status != ClosureStatus.READY:
        raise ClosureNotReadyError(
            f"{closure.operation_id}/{closure.channel}: closure status is {closure.status}, "
            f"issues: {closure.blocking_issues}"
        )


def _check_impl_refs(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    if len(closure.java_classes) >= len(closure.included_opstep_ids):
        return []
    return [_issue(ClosureStatus.BLOCKED_MISSING_IMPL_CLASS, closure.operation_id, "opStep without JavaClassRef")]


def _check_java_source_files(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    return [
        _issue(ClosureStatus.BLOCKED_MISSING_IMPL_CLASS, ref.fqcn, "Java source file missing")
        for ref in closure.java_classes
        if not Path(ref.source_file).exists()
    ]


def _check_formats_exist(
    closure: OperationClosure,
    conn: sqlite3.Connection,
    run_id: str,
) -> list[ClosureBlockingIssue]:
    issues = []
    for format_id in closure.formats.all_format_ids:
        if not _source_exists(conn, run_id, "format", format_id):
            issues.append(_issue(ClosureStatus.BLOCKED_MISSING_FORMAT, format_id, "Format not found"))
    return issues


def _check_tags_exist(
    closure: OperationClosure,
    conn: sqlite3.Connection,
    run_id: str,
) -> list[ClosureBlockingIssue]:
    issues = []
    for tag_name in closure.formats.formatter_tags:
        if not _tag_exists(conn, run_id, tag_name):
            issues.append(_issue(ClosureStatus.BLOCKED_UNKNOWN_TAG, tag_name, "Formatter tag not mapped"))
    for decorators in closure.formats.decorator_chains.values():
        for tag_name in decorators:
            if not _tag_exists(conn, run_id, tag_name):
                issues.append(_issue(ClosureStatus.BLOCKED_UNKNOWN_TAG, tag_name, "Decorator tag not mapped"))
    return issues


def _check_context_chain(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    if closure.context_chain:
        return []
    return [_issue(ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE, closure.context_id, "Context chain is unresolved")]


def _check_error_reply_format(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    if closure.return_body_switches and not closure.formats.error_reply_format_id:
        return [_issue(ClosureStatus.BLOCKED_MISSING_FORMAT, closure.operation_id, "csErrorReplyFormat is required")]
    return []


def _check_unresolved_formats(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    return [
        _issue(ClosureStatus.BLOCKED_MISSING_FORMAT, format_id, "Unresolved format reference")
        for format_id in closure.formats.unresolved_format_refs
    ]


def _check_routing_covers_return_codes(closure: OperationClosure) -> list[ClosureBlockingIssue]:
    issues = []
    for opstep_id, java_ref in zip(closure.included_opstep_ids, closure.java_classes):
        routing = closure.routing_graph.get(opstep_id, {})
        for rc in java_ref.return_codes:
            if f"on{rc}Do" not in routing and "onOtherDo" not in routing:
                issues.append(
                    _issue(
                        ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
                        opstep_id,
                        f"Latent routing gap: RC {rc} emitted by {java_ref.fqcn} has no routing rule in operation XML",
                    )
                )
    return issues


def _most_severe_status(issues: list[ClosureBlockingIssue]) -> ClosureStatus:
    if not issues:
        return ClosureStatus.READY
    issue_kinds = {issue.kind for issue in issues}
    for status in SEVERITY:
        if status in issue_kinds:
            return status
    return ClosureStatus.NEEDS_HUMAN_MAPPING


def _source_exists(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str) -> bool:
    return conn.execute(
        """
        SELECT 1 FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        LIMIT 1
        """,
        (run_id, kind, logical_id),
    ).fetchone() is not None


def _tag_exists(conn: sqlite3.Connection, run_id: str, tag_name: str) -> bool:
    return conn.execute(
        """
        SELECT 1 FROM tag_registry
        WHERE run_id = ? AND tag_name = ?
        LIMIT 1
        """,
        (run_id, tag_name),
    ).fetchone() is not None


def _issue(kind: ClosureStatus, entity_id: str, detail: str) -> ClosureBlockingIssue:
    return ClosureBlockingIssue(kind=kind, entity_id=entity_id, detail=detail)
