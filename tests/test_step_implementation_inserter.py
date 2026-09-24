from __future__ import annotations

import subprocess
from pathlib import Path

from agents.operation_assembly.step_implementation_inserter.agent import (
    PASSES,
    build_execute_body,
    replace_method_body,
    run_ibm_guard,
    run_step_implementation_inserter,
)
from models.conversion_models import ContextPlan, RoutingPlan, RoutingStep, SerializationPlan
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.context_plans import upsert_context_plan
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact
from tools.state_store_tools.routing_plans import upsert_routing_plan
from tools.state_store_tools.serialization_plans import upsert_serialization_plan


RUN_ID = "run-1"
TASK_ID = "task-step-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["javac"], returncode=returncode, stdout="", stderr=stderr)


def skeleton_source() -> str:
    return """
public class TransferFundsService {
    public TransferFundsResponse execute(String requestXml) throws Exception {
        var ctx = new TransferContext();
        throw new UnsupportedOperationException("not yet implemented");
    }

    private TransferFundsRequest deserializeRequest(String xml) {
        throw new UnsupportedOperationException("not yet implemented");
    }

    private void initializeContext(TransferContext ctx, TransferFundsRequest req) {
        throw new UnsupportedOperationException("not yet implemented");
    }

    private void enrichWithDbLookups(TransferContext ctx) {
        throw new UnsupportedOperationException("not yet implemented");
    }

    private String serializeReply(TransferFundsResponse reply) {
        throw new UnsupportedOperationException("not yet implemented");
    }

    private String serializeErrorReply(ErrorResponse err) {
        throw new UnsupportedOperationException("not yet implemented");
    }
}
"""


def routing_plan() -> RoutingPlan:
    return RoutingPlan(
        operation_id="TransferFunds",
        channel="INTERNET",
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="com.bank.StepA",
                transitions={"0": "end", "4": 1},
            ),
            RoutingStep(
                step_id="StepB",
                step_index=1,
                impl_class="com.bank.StepB",
                transitions={"0": "end"},
            ),
        ],
    )


def context_plan() -> ContextPlan:
    return ContextPlan(operation_id="TransferFunds", channel="INTERNET", context_class="TransferContext")


def serialization_plan() -> SerializationPlan:
    return SerializationPlan(operation_id="TransferFunds", channel="INTERNET")


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


def add_task(conn, max_retries: int = 3):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="StepImplementationInserterAgent",
        scope_type="operation",
        scope_id="TransferFunds",
        channel="INTERNET",
        target_language="java",
        status="pending",
        max_retries=max_retries,
        input_data={"operation_id": "TransferFunds"},
    )


def test_pass_1_only_modifies_deserialize_request():
    updated = replace_method_body(skeleton_source(), "deserializeRequest", ["return null;"])

    assert "private TransferFundsRequest deserializeRequest(String xml) {\n        return null;\n    }" in updated
    assert updated.count('throw new UnsupportedOperationException("not yet implemented");') == 5
    assert "private void initializeContext" in updated


def test_pass_3_execute_body_contains_routing_for_each_step():
    body = "\n".join(build_execute_body(routing_plan()))

    assert "int rc0 = stepA(ctx);" in body
    assert "if (rc0 == 0)" in body
    assert "if (rc0 == 4)" in body
    assert "int rc1 = stepB(ctx);" in body


def test_compile_failure_on_pass_2_triggers_retry(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task(conn)
    service_path = tmp_path / "Service.java"
    service_path.write_text(skeleton_source(), encoding="utf-8")
    calls = {"compile": 0, "pass2_errors": []}

    def fake_compile(path):
        calls["compile"] += 1
        if calls["compile"] == 2:
            return compiled(1, "pass2 compile error")
        return compiled(0)

    def generator(implementation_pass, current_class, routing, context, serialization, compiler_error):
        if implementation_pass.pass_number == 2:
            calls["pass2_errors"].append(compiler_error)
        return replace_method_body(current_class, implementation_pass.method_name, [f"// pass {implementation_pass.pass_number}"])

    monkeypatch.setattr(
        "agents.operation_assembly.step_implementation_inserter.agent._compile_java_source",
        fake_compile,
    )

    result = run_step_implementation_inserter(
        conn,
        TASK_ID,
        "TransferFunds",
        "INTERNET",
        RUN_ID,
        str(service_path),
        generator,
    )

    assert result == "compiled"
    assert calls["pass2_errors"] == [None, "pass2 compile error"]


def test_ibm_guard_after_pass_6_triggers_execute_retry(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task(conn)
    service_path = tmp_path / "Service.java"
    service_path.write_text(skeleton_source(), encoding="utf-8")
    execute_errors = []

    def generator(implementation_pass, current_class, routing, context, serialization, compiler_error):
        if implementation_pass.method_name == "execute":
            execute_errors.append(compiler_error)
            body = ["return null;"]
            if compiler_error is None:
                body = ["String bad = \"com.ibm.Legacy\";", "return null;"]
            return replace_method_body(current_class, "execute", body)
        return replace_method_body(current_class, implementation_pass.method_name, [f"// pass {implementation_pass.pass_number}"])

    monkeypatch.setattr(
        "agents.operation_assembly.step_implementation_inserter.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = run_step_implementation_inserter(
        conn,
        TASK_ID,
        "TransferFunds",
        "INTERNET",
        RUN_ID,
        str(service_path),
        generator,
        forbidden=["com.ibm"],
    )

    assert result == "compiled"
    assert execute_errors[-1] == "IBM dependency guard found: com.ibm"


def test_max_retries_exceeded_sets_compile_failed(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task(conn, max_retries=2)
    service_path = tmp_path / "Service.java"
    service_path.write_text(skeleton_source(), encoding="utf-8")

    monkeypatch.setattr(
        "agents.operation_assembly.step_implementation_inserter.agent._compile_java_source",
        lambda path: compiled(1, "compile failed"),
    )

    result = run_step_implementation_inserter(
        conn,
        TASK_ID,
        "TransferFunds",
        "INTERNET",
        RUN_ID,
        str(service_path),
        lambda implementation_pass, current_class, routing, context, serialization, compiler_error: current_class,
    )

    task = get_agent_task(conn, TASK_ID)
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:step_implementation:TransferFunds:{TASK_ID}")
    assert result == "compile_failed"
    assert task["status"] == "blocked"
    assert task["blocking_reason"] == "compile_failed"
    assert artifact["blocking_reason"] == "compile_failed"


def test_run_ibm_guard_returns_forbidden_patterns():
    assert run_ibm_guard("import com.ibm.Legacy;", ["com.ibm", "javax.ejb"]) == ["com.ibm"]
