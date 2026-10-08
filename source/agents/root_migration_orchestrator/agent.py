from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from agents.human_approval.agent import HumanApprovalAgent
from models.common_models import RunConfig
from models.migration_models import MigrationBatch, MigrationTaskPacket
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.runs import get_run, update_run_status

try:
    from google.adk.agents import SequentialAgent
except ImportError:

    class SequentialAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


@dataclass(frozen=True)
class BatchResult:
    """Outcome counts for one migration batch phase."""

    batch_id: str
    phase: str
    success_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0


PhaseRunner = Callable[[sqlite3.Connection, MigrationTaskPacket, RunConfig], str]


def build_conversion_phase(run_config: RunConfig) -> SequentialAgent:
    """Build the conversion phase wrapper for ADK orchestration."""
    return SequentialAgent(
        name="conversion_phase",
        description=f"Converts READY closures for run {run_config.run_id}.",
        sub_agents=[],
    )


def build_assembly_phase(run_config: RunConfig) -> SequentialAgent:
    """Build the operation assembly phase wrapper for ADK orchestration."""
    return SequentialAgent(
        name="assembly_phase",
        description=f"Assembles READY operations for run {run_config.run_id}.",
        sub_agents=[],
    )


def process_batch(
    conn: sqlite3.Connection,
    batch: MigrationBatch,
    run_config: RunConfig,
    phase: str | PhaseRunner,
) -> BatchResult:
    """Process every task in a batch, continuing after blocked operations."""
    phase_name = phase if isinstance(phase, str) else getattr(phase, "__name__", "phase")
    success_count = 0
    failed_count = 0
    blocked_count = 0
    for packet in batch.task_packets:
        status = phase(conn, packet, run_config) if callable(phase) else packet.status.value
        upsert_agent_task(
            conn,
            task_id=packet.task_id,
            run_id=packet.run_id,
            agent_name=phase_name,
            scope_type="operation",
            scope_id=packet.operation_id,
            channel=packet.channel,
            target_language=packet.target_language.value,
            status=status,
        )
        if status in {"completed", "validated"}:
            success_count += 1
        elif status == "blocked":
            blocked_count += 1
        else:
            failed_count += 1
    return BatchResult(
        batch_id=batch.batch_id,
        phase=phase_name,
        success_count=success_count,
        failed_count=failed_count,
        blocked_count=blocked_count,
    )


def find_resume_point(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """Find the earliest pending or needs_rerun task for a resumable run."""
    run = get_run(conn, run_id)
    row = conn.execute(
        """
        SELECT *
        FROM agent_tasks
        WHERE run_id = ? AND status IN ('needs_rerun', 'pending')
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["current_phase"] = run["current_phase"] if run else None
    return result


def run_root_pipeline_with_gates(
    conn: sqlite3.Connection,
    run_id: str,
    gate_reports: list[tuple[int, str]],
    approval_agent: HumanApprovalAgent,
) -> bool:
    """Run human gates in order and stop the run on rejection."""
    for gate_number, report in gate_reports:
        if not approval_agent.present_gate(gate_number, report, run_id):
            update_run_status(conn, run_id, "stopped", current_phase=f"gate_{gate_number}_rejected")
            return False
    update_run_status(conn, run_id, "completed", current_phase="complete")
    return True


def mark_phase_started(conn: sqlite3.Connection, run_id: str, phase: str) -> None:
    """Record the current phase for resumable orchestration."""
    update_run_status(conn, run_id, "in_progress", current_phase=phase)


root_migration_orchestrator = SequentialAgent(
    name="RootMigrationOrchestratorAgent",
    description="Orchestrates the full WSBCC migration pipeline.",
    sub_agents=[],
)
