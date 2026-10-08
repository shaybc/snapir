from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from tools.conversion_tools.context_hierarchy_resolver_tool import require_inventory_complete
from tools.state_store_tools._json import dumps, loads, utc_now


@dataclass
class ClassificationSummary:
    shared_formats: int = 0
    shared_classes: int = 0
    shared_contexts: int = 0
    xml_contract_candidates: int = 0
    total_processed: int = 0


def run_shared_artifact_classification(
    conn: sqlite3.Connection, run_id: str
) -> ClassificationSummary:
    require_inventory_complete(conn, run_id)
    summary = ClassificationSummary()
    rows = conn.execute(
        """
        SELECT artifact_id, kind, logical_id, used_by_count, metadata_json
        FROM source_artifacts
        WHERE run_id = ?
        ORDER BY artifact_id
        """,
        (run_id,),
    ).fetchall()
    for row in rows:
        summary.total_processed += 1
        kind = row["kind"]
        shared = int(row["used_by_count"]) > 1 and kind in {"format", "java_class", "context"}
        metadata = loads(row["metadata_json"], {}) or {}
        is_contract = kind == "format" and _is_xml_contract_candidate(row["logical_id"])
        if is_contract:
            metadata["xml_contract_candidate"] = True
            summary.xml_contract_candidates += 1
        if shared:
            if kind == "format":
                summary.shared_formats += 1
            elif kind == "java_class":
                summary.shared_classes += 1
            elif kind == "context":
                summary.shared_contexts += 1
        conn.execute(
            """
            UPDATE source_artifacts
            SET shared = ?, metadata_json = ?, updated_at = ?
            WHERE artifact_id = ?
            """,
            (int(shared), dumps(metadata), utc_now(), row["artifact_id"]),
        )
    conn.commit()
    return summary


def _is_xml_contract_candidate(logical_id: str) -> bool:
    return (
        logical_id.endswith("HeaderFmt")
        or logical_id.endswith("ErrorFmt")
        or logical_id.endswith("StandardError")
        or "StandardError" in logical_id
    )
