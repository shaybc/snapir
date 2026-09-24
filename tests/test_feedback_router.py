from __future__ import annotations

from models.common_models import RunConfig, RunMode, TargetLanguage
from models.conversion_models import ConversionStatus, ValidationFailureClass
from models.registry_models import ComponentRegistryRecord
from models.validation_models import ValidationReport
from tools.artifact_registry_tools.component_registry import register_component
from tools.routing_tools.feedback_router import FeedbackRouter
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.generated_artifacts import get_generated_artifact, upsert_generated_artifact
from tools.state_store_tools.runs import upsert_run


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config(max_retries: int = 3) -> RunConfig:
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
        max_agent_task_retries=max_retries,
        max_parallel_conversion_workers=1,
        max_parallel_llm_tasks=1,
        max_parallel_build_tasks=1,
        max_operations_per_batch=2,
        model_name="test",
        model_base_url="",
        auto_rerun_impacted_operations=True,
    )


def report(operation_id: str, failure_class: ValidationFailureClass, attempt_number: int = 0) -> ValidationReport:
    return ValidationReport(
        run_id=RUN_ID,
        operation_id=operation_id,
        target_language=TargetLanguage.java,
        build_passed=True,
        test_passed=False,
        xml_compat_passed=False,
        ibm_guard_passed=True,
        behavior_equiv_passed=False,
        failure_class=failure_class,
        attempt_number=attempt_number,
    )


def add_generated(conn, operation_id: str):
    upsert_generated_artifact(
        conn,
        artifact_id=f"gen-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel="INTERNET",
        target_language="java",
        artifact_kind="service",
        generated_path=f"generated/{operation_id}",
        status="converted",
    )


def test_routing_mismatch_routes_to_step_implementation_pass_3():
    conn = memory_conn()
    add_generated(conn, "OpA")
    action = FeedbackRouter().route(conn, report("OpA", ValidationFailureClass.routing_mismatch), run_config())

    assert action.target_agent == "StepImplementationInserterAgent"
    assert "pass 3" in action.additional_instructions


def test_shared_component_gap_triggers_cascade_invalidation_for_dependents():
    conn = memory_conn()
    upsert_run(conn, run_id=RUN_ID, run_mode="single_channel", run_config=run_config())
    add_generated(conn, "OpA")
    add_generated(conn, "OpB")
    register_component(
        conn,
        ComponentRegistryRecord(
            component_id="component-1",
            artifact_kind="ibm_java",
            logical_id="SharedStep",
            source_path="",
            source_hash="hash",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="common-lib/SharedStep.java",
            status=ConversionStatus.validated,
            used_by_operations=["OpA", "OpB"],
            used_by_validated_operations=2,
        ),
    )
    router = FeedbackRouter()
    action = router.route(conn, report("OpA", ValidationFailureClass.shared_component_gap), run_config())

    router.apply_feedback(conn, action, run_config())

    assert get_generated_artifact(conn, "gen-OpA")["status"] == "needs_rerun"
    assert get_generated_artifact(conn, "gen-OpB")["status"] == "needs_rerun"


def test_max_retries_exceeded_sets_needs_human_review():
    conn = memory_conn()
    add_generated(conn, "OpA")
    upsert_agent_task(
        conn,
        run_id=RUN_ID,
        agent_name="JavaValidationAgent",
        scope_type="operation",
        scope_id="OpA",
        channel="INTERNET",
        status="failed",
    )
    router = FeedbackRouter()
    action = router.route(conn, report("OpA", ValidationFailureClass.equivalence_gap, attempt_number=3), run_config(max_retries=3))

    router.apply_feedback(conn, action, run_config(max_retries=3))

    artifact = get_generated_artifact(conn, "gen-OpA")
    task = get_agent_task(conn, f"{RUN_ID}:JavaValidationAgent:operation:OpA:INTERNET:any:v1")
    assert artifact["status"] == "needs_human_review"
    assert artifact["blocking_reason"] == "max_retries_exceeded"
    assert task["status"] == "needs_human_review"


def test_validation_fixture_gap_does_not_rerun_conversion_agents():
    conn = memory_conn()
    add_generated(conn, "OpA")
    action = FeedbackRouter().route(conn, report("OpA", ValidationFailureClass.validation_fixture_gap), run_config())

    assert action.target_agent == "validation_tools"
    assert "IbmJavaCleanerAgent" not in action.target_agent
