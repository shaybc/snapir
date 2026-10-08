from __future__ import annotations

import subprocess

from agents.operation_assembly.service_skeleton_generator.agent import (
    build_service_skeleton_source,
    load_service_skeleton_plans,
    run_service_skeleton_generator_task,
    write_and_compile_service_skeleton,
)
from models.conversion_models import (
    ContextPlan,
    DbLookupRequirement,
    RoutingPlan,
    SerializationPlan,
)
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.context_plans import upsert_context_plan
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact
from tools.state_store_tools.routing_plans import upsert_routing_plan
from tools.state_store_tools.serialization_plans import upsert_serialization_plan


RUN_ID = "run-1"
TASK_ID = "task-skeleton-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["javac"], returncode=returncode, stdout="", stderr=stderr)


def routing_plan() -> RoutingPlan:
    return RoutingPlan(operation_id="TransferFunds", channel="INTERNET", has_finally_step=False)


def context_plan() -> ContextPlan:
    return ContextPlan(operation_id="TransferFunds", channel="INTERNET", context_class="TransferContext")


def serialization_plan() -> SerializationPlan:
    return SerializationPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        db_lookups=[
            DbLookupRequirement(
                field_name="BranchName",
                from_table="BRANCH",
                from_column="NAME",
                key_value_field="BranchId",
            )
        ],
    )


def store_plans(conn):
    upsert_routing_plan(
        conn,
        operation_id="TransferFunds",
        channel="INTERNET",
        run_id=RUN_ID,
        plan=routing_plan().model_dump(mode="json"),
        status="ready",
    )
    upsert_context_plan(
        conn,
        operation_id="TransferFunds",
        channel="INTERNET",
        run_id=RUN_ID,
        plan=context_plan().model_dump(mode="json"),
        status="ready",
    )
    upsert_serialization_plan(
        conn,
        operation_id="TransferFunds",
        channel="INTERNET",
        run_id=RUN_ID,
        plan=serialization_plan().model_dump(mode="json"),
        status="ready",
    )


def add_task(conn):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="ServiceSkeletonGeneratorAgent",
        scope_type="operation",
        scope_id="TransferFunds",
        channel="INTERNET",
        target_language="java",
        status="pending",
        input_data={"operation_id": "TransferFunds"},
    )


def skeleton_source() -> str:
    return build_service_skeleton_source(
        "TransferFunds",
        "INTERNET",
        routing_plan(),
        context_plan(),
        serialization_plan(),
    )


def test_generated_skeleton_has_six_methods_with_stub_bodies():
    source = skeleton_source()

    signatures = [
        "public TransferFundsResponse execute(String requestXml) throws Exception",
        "private TransferFundsRequest deserializeRequest(String xml)",
        "private void initializeContext(TransferContext ctx, TransferFundsRequest req)",
        "private void enrichWithDbLookups(TransferContext ctx)",
        "private String serializeReply(TransferFundsResponse reply)",
        "private String serializeErrorReply(ErrorResponse err)",
    ]
    for signature in signatures:
        assert signature in source
    assert source.count('throw new UnsupportedOperationException("not yet implemented");') == 6


def test_constructor_injection_for_db_lookup_repositories():
    source = skeleton_source()

    assert "private final BranchNameRepository branchNameRepository;" in source
    assert "@Autowired" in source
    assert "public TransferFundsService(BranchNameRepository branchNameRepository)" in source
    assert "this.branchNameRepository = branchNameRepository;" in source


def test_context_instantiated_inside_execute_not_as_field():
    source = skeleton_source()

    assert "var ctx = new TransferContext();" in source
    assert "private TransferContext ctx;" not in source


def test_load_service_skeleton_plans_reads_stored_plans():
    conn = memory_conn()
    store_plans(conn)

    routing, context, serialization = load_service_skeleton_plans(conn, "TransferFunds", "INTERNET", RUN_ID)

    assert routing.operation_id == "TransferFunds"
    assert context.context_class == "TransferContext"
    assert serialization.db_lookups[0].field_name == "BranchName"


def test_generated_skeleton_compiles_with_stub_bodies(monkeypatch, tmp_path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.operation_assembly.service_skeleton_generator.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = write_and_compile_service_skeleton(
        conn,
        TASK_ID,
        skeleton_source(),
        "TransferFunds",
        "INTERNET",
        RUN_ID,
        output_root=str(tmp_path),
    )

    artifact_id = f"{RUN_ID}:service_skeleton:TransferFunds:{TASK_ID}"
    artifact = get_native_java_artifact(conn, artifact_id)
    assert result == "compiled"
    assert get_agent_task(conn, TASK_ID)["status"] == "completed"
    assert artifact["status"] == "converted"
    assert artifact["compiles"] == 1
    assert (tmp_path / "INTERNET" / "TransferFunds" / "Service.java").exists()


def test_mock_service_skeleton_runner_uses_loaded_plans(monkeypatch, tmp_path):
    conn = memory_conn()
    store_plans(conn)
    add_task(conn)
    monkeypatch.setattr(
        "agents.operation_assembly.service_skeleton_generator.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = run_service_skeleton_generator_task(
        conn,
        TASK_ID,
        "TransferFunds",
        "INTERNET",
        RUN_ID,
        output_root=str(tmp_path),
    )

    assert result == "compiled"
