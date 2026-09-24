from __future__ import annotations

from agents.human_approval.agent import HumanApprovalAgent
from agents.root_migration_orchestrator.agent import (
    find_resume_point,
    process_batch,
    run_root_pipeline_with_gates,
)
from models.common_models import RunConfig, RunMode, TargetLanguage, TaskStatus
from models.migration_models import MigrationBatch, MigrationTaskPacket, OperationGrouping
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.runs import get_run, upsert_run


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config() -> RunConfig:
    return RunConfig(
        run_id=RUN_ID,
        run_mode=RunMode.single_channel,
        source_root="input",
        vault_root="vault",
        output_root="generated",
        db_path="state.db",
        target_channels=["INTERNET"],
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=1,
        max_parallel_llm_tasks=1,
        max_parallel_build_tasks=1,
        max_operations_per_batch=2,
        model_name="test",
        model_base_url="",
        auto_rerun_impacted_operations=True,
    )


def packet(task_id: str, operation_id: str) -> MigrationTaskPacket:
    return MigrationTaskPacket(
        task_id=task_id,
        run_id=RUN_ID,
        operation_id=operation_id,
        channel="INTERNET",
        target_language=TargetLanguage.java,
        group=OperationGrouping.one_step,
        status=TaskStatus.pending,
    )


def test_gate1_rejection_stops_the_run():
    conn = memory_conn()
    upsert_run(conn, run_id=RUN_ID, run_mode="single_channel", status="started")
    approval = HumanApprovalAgent(conn=conn, input_fn=lambda prompt: "no", output_fn=lambda report: None)

    result = run_root_pipeline_with_gates(conn, RUN_ID, [(1, "Gate 1 report")], approval)

    assert result is False
    run = get_run(conn, RUN_ID)
    assert run["status"] == "stopped"
    assert run["current_phase"] == "gate_1_rejected"


def test_batch_with_one_blocked_operation_continues_processing_others():
    conn = memory_conn()
    batch = MigrationBatch(
        batch_id="batch-1",
        run_id=RUN_ID,
        task_packets=[packet("task-1", "OpA"), packet("task-2", "OpB")],
        is_pilot=True,
        status=TaskStatus.pending,
    )

    def phase(conn, packet, config):
        return "blocked" if packet.operation_id == "OpA" else "completed"

    result = process_batch(conn, batch, run_config(), phase)

    assert result.blocked_count == 1
    assert result.success_count == 1


def test_resume_finds_correct_restart_point_after_simulated_crash():
    conn = memory_conn()
    upsert_run(conn, run_id=RUN_ID, run_mode="single_channel", status="in_progress", current_phase="conversion")
    upsert_agent_task(
        conn,
        task_id="task-complete",
        run_id=RUN_ID,
        agent_name="phase",
        scope_type="operation",
        scope_id="OpA",
        channel="INTERNET",
        status="completed",
    )
    upsert_agent_task(
        conn,
        task_id="task-pending",
        run_id=RUN_ID,
        agent_name="phase",
        scope_type="operation",
        scope_id="OpB",
        channel="INTERNET",
        status="pending",
    )

    resume = find_resume_point(conn, RUN_ID)

    assert resume["task_id"] == "task-pending"
    assert resume["current_phase"] == "conversion"
