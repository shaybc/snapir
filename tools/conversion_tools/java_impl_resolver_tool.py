from __future__ import annotations

import sqlite3

from models.conversion_models import ClosureBlockingIssue, ClosureStatus, JavaClassRef
from tools.java_analysis_tools.java_source_reader import resolve_source_path
from tools.state_store_tools._json import loads


def resolve_java_impls(
    conn: sqlite3.Connection,
    opstep_ids: list[str],
    run_id: str,
    composer_root: str,
) -> tuple[list[JavaClassRef], list[ClosureBlockingIssue]]:
    """Resolve opStep implementation classes from vault metadata and source files."""
    refs: list[JavaClassRef] = []
    issues: list[ClosureBlockingIssue] = []
    seen: set[str] = set()
    for opstep_id in opstep_ids:
        opstep = _source_artifact(conn, run_id, "opStep", opstep_id)
        metadata = loads(opstep["metadata_json"], {}) if opstep else {}
        fqcn = _impl_class_for_opstep(conn, metadata, run_id)
        if not fqcn:
            issues.append(_missing_impl(opstep_id, "Missing implClass"))
            continue
        class_artifact = _source_artifact(conn, run_id, "java_class", fqcn)
        if class_artifact is None:
            issues.append(_missing_impl(fqcn, "ImplClass not found in vault"))
            continue
        source_file = resolve_source_path(composer_root, fqcn)
        if source_file is None:
            issues.append(_missing_impl(fqcn, "ImplClass source file not found on disk"))
            continue
        class_metadata = loads(class_artifact["metadata_json"], {}) or {}
        if fqcn in seen:
            continue
        refs.append(
            JavaClassRef(
                fqcn=fqcn,
                source_file=source_file,
                parent_class=class_metadata.get("parent_class"),
                interfaces=list(class_metadata.get("interfaces", [])),
                has_ibm_dependency=bool(class_metadata.get("has_ibm_dependency", False)),
                ibm_imports=list(class_metadata.get("ibm_imports", [])),
                return_codes=dict(class_metadata.get("return_codes", {})),
                shared=bool(class_artifact["shared"]),
            )
        )
        seen.add(fqcn)
    return refs, issues


def _impl_class_for_opstep(conn: sqlite3.Connection, metadata: dict, run_id: str) -> str | None:
    impl_class = metadata.get("impl_class")
    if impl_class:
        return str(impl_class)
    tag_name = metadata.get("tag_name") or metadata.get("tag") or metadata.get("id")
    if not tag_name:
        return None
    row = conn.execute(
        """
        SELECT fqcn FROM tag_registry
        WHERE tag_name = ? AND run_id = ?
        LIMIT 1
        """,
        (tag_name, run_id),
    ).fetchone()
    return row["fqcn"] if row else None


def _source_artifact(conn: sqlite3.Connection, run_id: str, kind: str, logical_id: str):
    return conn.execute(
        """
        SELECT * FROM source_artifacts
        WHERE run_id = ? AND kind = ? AND logical_id = ?
        """,
        (run_id, kind, logical_id),
    ).fetchone()


def _missing_impl(entity_id: str, detail: str) -> ClosureBlockingIssue:
    return ClosureBlockingIssue(
        kind=ClosureStatus.BLOCKED_MISSING_IMPL_CLASS,
        entity_id=entity_id,
        detail=detail,
    )
