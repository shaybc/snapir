from __future__ import annotations

from agents.java_validation.agent import JavaBuildResult, run_java_validation
from models.conversion_models import RoutingPlan, RoutingStep, ValidationFailureClass
from models.validation_models import TraceComparisonResult, ValidationPlan
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.generated_artifacts import get_generated_artifact, upsert_generated_artifact


RUN_ID = "run-1"
ARTIFACT_ID = "artifact-java-service"
OPERATION_ID = "TransferFunds"
CHANNEL = "INTERNET"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def add_artifact(conn):
    upsert_generated_artifact(
        conn,
        artifact_id=ARTIFACT_ID,
        run_id=RUN_ID,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        target_language="java",
        artifact_kind="service",
        generated_path="generated",
        status="converted",
        attempt_number=1,
    )


def routing_plan() -> RoutingPlan:
    return RoutingPlan(
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        has_finally_step=False,
        steps=[
            RoutingStep(step_id="StepA", step_index=0, impl_class="StepA", transitions={"0": "end"})
        ],
    )


def passed_trace() -> TraceComparisonResult:
    return TraceComparisonResult(
        matched=True,
        step_sequence_match=True,
        rc_per_step_match=True,
        context_writes_match=True,
        reply_format_match=True,
        final_xml_match=True,
    )


def failed_trace() -> TraceComparisonResult:
    return TraceComparisonResult(
        matched=False,
        step_sequence_match=False,
        rc_per_step_match=True,
        context_writes_match=True,
        reply_format_match=True,
        final_xml_match=True,
        failure_class=ValidationFailureClass.routing_mismatch,
    )


def test_ibm_pattern_found_in_step_2_stops_validation():
    conn = memory_conn()
    add_artifact(conn)
    calls = {"trace": 0}

    report = run_java_validation(
        conn,
        artifact_id=ARTIFACT_ID,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        generated_path="generated",
        routing_plan=routing_plan(),
        compile_validator=lambda path: JavaBuildResult(0),
        ibm_guard_validator=lambda path, forbidden: ["Service.java:1:com.ibm"],
        trace_runner=lambda *args: calls.__setitem__("trace", calls["trace"] + 1) or [],
    )

    artifact = get_generated_artifact(conn, ARTIFACT_ID)
    assert report.ibm_guard_passed is False
    assert artifact["status"] == "blocked"
    assert artifact["blocking_reason"] == "ibm_dependency_found"
    assert calls["trace"] == 0


def test_routing_mismatch_from_trace_sets_validation_report_failure_class():
    conn = memory_conn()
    add_artifact(conn)

    report = run_java_validation(
        conn,
        artifact_id=ARTIFACT_ID,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        generated_path="generated",
        routing_plan=routing_plan(),
        validation_plan=ValidationPlan(operation_id=OPERATION_ID),
        compile_validator=lambda path: JavaBuildResult(0),
        ibm_guard_validator=lambda path, forbidden: [],
        trace_runner=lambda *args: [failed_trace()],
    )

    assert report.failure_class == ValidationFailureClass.routing_mismatch
    assert get_generated_artifact(conn, ARTIFACT_ID)["blocking_reason"] == "routing_mismatch"


def test_all_seven_steps_pass_marks_generated_artifact_validated():
    conn = memory_conn()
    add_artifact(conn)

    report = run_java_validation(
        conn,
        artifact_id=ARTIFACT_ID,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        generated_path="generated",
        routing_plan=routing_plan(),
        validation_plan=ValidationPlan(operation_id=OPERATION_ID),
        compile_validator=lambda path: JavaBuildResult(0),
        ibm_guard_validator=lambda path, forbidden: [],
        trace_runner=lambda *args: [passed_trace()],
        performance_runner=lambda base_url, request_xml: {"p50_ms": 1, "p95_ms": 2},
    )

    artifact = get_generated_artifact(conn, ARTIFACT_ID)
    assert report.failure_class is None
    assert report.behavior_equiv_passed is True
    assert artifact["status"] == "validated"
    assert artifact["blocking_reason"] is None
