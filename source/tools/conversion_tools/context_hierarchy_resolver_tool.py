from __future__ import annotations

import sqlite3

from models.conversion_models import ContextHierarchy
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.context_hierarchies import (
    get_context_hierarchy as get_context_hierarchy_row,
    upsert_context_hierarchy,
)
from tools.state_store_tools._json import loads
from tools.state_store_tools.runs import get_run


INVENTORY_COMPLETE = "INVENTORY_COMPLETE=true"


class PreconditionError(RuntimeError):
    pass


def require_inventory_complete(conn: sqlite3.Connection, run_id: str) -> None:
    run = get_run(conn, run_id)
    if run is None or run.get("current_phase") != INVENTORY_COMPLETE:
        raise PreconditionError("INVENTORY_COMPLETE is required before this tool runs")


def build_all_context_hierarchies(conn: sqlite3.Connection, run_id: str) -> list[ContextHierarchy]:
    require_inventory_complete(conn, run_id)
    contexts = _load_context_metadata(conn, run_id)
    hierarchies = []
    for context_id in sorted(contexts):
        hierarchy = _build_context_hierarchy(context_id, contexts)
        upsert_context_hierarchy(
            conn,
            context_id=hierarchy.context_id,
            run_id=run_id,
            chain=hierarchy.chain,
            root_id=hierarchy.root_id,
            has_cycle=hierarchy.has_cycle,
        )
        if hierarchy.has_cycle:
            upsert_agent_task(
                conn,
                run_id=run_id,
                agent_name="ContextHierarchyResolverTool",
                scope_type="context",
                scope_id=context_id,
                channel="all",
                target_language="any",
                status="needs_human_review",
                blocking_reason="context_cycle",
                output_data=hierarchy.model_dump(mode="json"),
            )
        hierarchies.append(hierarchy)
    return hierarchies


def get_context_hierarchy(
    conn: sqlite3.Connection, context_id: str, run_id: str
) -> ContextHierarchy:
    row = get_context_hierarchy_row(conn, context_id, run_id)
    if row is None:
        raise KeyError(f"Context hierarchy not found: {context_id}")
    return ContextHierarchy(
        context_id=row["context_id"],
        chain=row["chain_json"],
        root_id=row["root_id"],
        has_cycle=bool(row["has_cycle"]),
    )


def _load_context_metadata(conn: sqlite3.Connection, run_id: str) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT logical_id, metadata_json
        FROM source_artifacts
        WHERE run_id = ? AND kind = 'context'
        """,
        (run_id,),
    ).fetchall()
    return {
        row["logical_id"]: loads(row["metadata_json"], {}) or {}
        for row in rows
    }


def _build_context_hierarchy(context_id: str, contexts: dict[str, dict]) -> ContextHierarchy:
    chain: list[str] = []
    seen: set[str] = set()
    current_id: str | None = context_id
    has_cycle = False

    while current_id:
        if current_id in seen:
            has_cycle = True
            break
        seen.add(current_id)
        chain.append(current_id)
        parent_id = _parent_id(contexts.get(current_id, {}))
        if parent_id is None or parent_id not in contexts:
            break
        current_id = parent_id

    root_id = chain[-1] if chain else context_id
    return ContextHierarchy(
        context_id=context_id,
        chain=chain,
        root_id=root_id,
        has_cycle=has_cycle,
    )


def _parent_id(metadata: dict) -> str | None:
    parent = metadata.get("parent_id")
    if parent is None:
        parent = metadata.get("parent")
    if parent is None:
        return None
    parent = str(parent).strip()
    if parent == "" or parent.lower() in {"nil", "none", "null"}:
        return None
    return parent
