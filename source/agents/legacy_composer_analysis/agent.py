from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from typing import Any

from models.common_models import RunConfig
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.invalidation import cascade_invalidation, detect_hash_changes
from tools.state_store_tools.runs import update_run_status

try:
    from google.adk.agents import SequentialAgent
except ImportError:

    @dataclass
    class SequentialAgent:
        name: str
        description: str
        sub_agents: list


AGENT_NAME = "LegacyComposerAnalysisAgent"
INVENTORY_COMPLETE = "INVENTORY_COMPLETE=true"


legacy_composer_analysis_agent = SequentialAgent(
    name=AGENT_NAME,
    description="Reads the composer-mapper vault and populates the DB.",
    sub_agents=[],
)


def run_legacy_composer_analysis(
    conn: sqlite3.Connection,
    run_config: RunConfig,
) -> dict[str, Any]:
    task_id = _task_id(run_config.run_id)
    try:
        summary = import_vault(conn, run_config.vault_root, run_config)
        upsert_agent_task(
            conn,
            task_id=task_id,
            run_id=run_config.run_id,
            agent_name=AGENT_NAME,
            scope_type="run",
            scope_id=run_config.run_id,
            channel="all",
            target_language="any",
            status="completed",
            output_data={"import_summary": asdict(summary)},
        )
    except Exception as exc:
        upsert_agent_task(
            conn,
            task_id=task_id,
            run_id=run_config.run_id,
            agent_name=AGENT_NAME,
            scope_type="run",
            scope_id=run_config.run_id,
            channel="all",
            target_language="any",
            status="failed",
            error_message=str(exc),
        )
        raise

    changes = detect_hash_changes(conn, run_config.run_id)
    invalidation_summary = cascade_invalidation(conn, run_config.run_id, changes)
    if changes and not run_config.auto_rerun_impacted_operations:
        update_run_status(
            conn,
            run_config.run_id,
            "paused_awaiting_operator",
            current_phase=_impact_report(invalidation_summary),
        )
        return {
            "import_summary": asdict(summary),
            "hash_changes": len(changes),
            "invalidation_summary": asdict(invalidation_summary),
            "paused": True,
        }

    update_run_status(
        conn,
        run_config.run_id,
        "started",
        current_phase=INVENTORY_COMPLETE,
    )
    return {
        "import_summary": asdict(summary),
        "hash_changes": len(changes),
        "invalidation_summary": asdict(invalidation_summary),
        "paused": False,
    }


def _task_id(run_id: str) -> str:
    return f"{run_id}:{AGENT_NAME}:run:{run_id}:all:any:v1"


def _impact_report(summary) -> str:
    return (
        "paused_awaiting_operator: "
        f"changed={summary.changed}, "
        f"stale_conversions={summary.stale_conversions}, "
        f"stale_operations={summary.stale_operations}, "
        f"stale_services={summary.stale_services}"
    )
