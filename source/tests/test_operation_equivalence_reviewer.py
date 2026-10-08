from __future__ import annotations

from pathlib import Path

from agents.operation_assembly.operation_equivalence_reviewer.agent import (
    build_human_gate3_report,
    review_operation_equivalence,
    run_operation_equivalence_reviewer,
)
from models.conversion_models import (
    ContextPlan,
    EquivalenceReviewResult,
    InitEntry,
    ParseStep,
    RoutingPlan,
    RoutingStep,
    SerializationPlan,
)
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.context_plans import upsert_context_plan
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact, upsert_native_java_artifact
from tools.state_store_tools.routing_plans import upsert_routing_plan
from tools.state_store_tools.serialization_plans import upsert_serialization_plan


RUN_ID = "run-1"
TASK_ID = "task-review-1"
OPERATION_ID = "TransferFunds"
CHANNEL = "INTERNET"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def routing_plan() -> RoutingPlan:
    return RoutingPlan(
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        has_finally_step=False,
        steps=[
            RoutingStep(
                step_id="StepA",
                step_index=0,
                impl_class="com.bank.StepA",
                transitions={"0": "end", "4": 1},
                return_body_switches={"on4Return": "ErrorResponse"},
            ),
        ],
    )


def context_plan() -> ContextPlan:
    return ContextPlan(
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        context_class="TransferContext",
        init_sequence=[InitEntry(field_name="accountId", source="request", value_or_expression="req.accountId")],
    )


def serialization_plan() -> SerializationPlan:
    return SerializationPlan(
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        request_parsing=[
            ParseStep(
                field_name="accountId",
                xml_path="/request/accountId",
                context_field="accountId",
                java_type="String",
            )
        ],
    )


def service_source(include_rc4: bool = True) -> str:
    rc4 = "if (rc0 == 4) { return serializeErrorReply(on4Return); }" if include_rc4 else ""
    return f"""
public class TransferFundsService {{
    public TransferFundsResponse execute(String requestXml) throws Exception {{
        var ctx = new TransferContext();
        var req = deserializeRequest(requestXml);
        initializeContext(ctx, req);
        int rc0 = stepA(ctx);
        if (rc0 == 0) {{ return null; }}
        {rc4}
        return null;
    }}

    private TransferFundsRequest deserializeRequest(String xml) {{
        var req = new TransferFundsRequest();
        req.accountId = xml;
        return req;
    }}

    private void initializeContext(TransferContext ctx, TransferFundsRequest req) {{
        ctx.accountId = req.accountId;
    }}

    private void enrichWithDbLookups(TransferContext ctx) {{
    }}

    private String serializeReply(TransferFundsResponse reply) {{
        return "";
    }}

    private String serializeErrorReply(ErrorResponse err) {{
        return "on4Return";
    }}
}}
"""


def store_plans(conn):
    upsert_routing_plan(
        conn,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        plan=routing_plan().model_dump(mode="json"),
        status="ready",
    )
    upsert_context_plan(
        conn,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        plan=context_plan().model_dump(mode="json"),
        status="ready",
    )
    upsert_serialization_plan(
        conn,
        operation_id=OPERATION_ID,
        channel=CHANNEL,
        run_id=RUN_ID,
        plan=serialization_plan().model_dump(mode="json"),
        status="ready",
    )


def add_task_and_artifact(conn):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="OperationEquivalenceReviewAgent",
        scope_type="operation",
        scope_id=OPERATION_ID,
        channel=CHANNEL,
        target_language="java",
        status="pending",
        max_retries=3,
    )
    upsert_native_java_artifact(
        conn,
        artifact_id=f"{RUN_ID}:step_implementation:{OPERATION_ID}:{TASK_ID}",
        run_id=RUN_ID,
        conversion_id=OPERATION_ID,
        kind="xml_operation",
        logical_id=OPERATION_ID,
        artifact_path="Service.java",
        compiles=True,
        review_status="pending",
        status="converted",
    )


def result(status: str, issue: str = "missing") -> EquivalenceReviewResult:
    return EquivalenceReviewResult(
        operation_id=OPERATION_ID,
        missing_steps=[],
        missing_rc_branches=[issue] if status != "approved" else [],
        context_mutation_issues=[],
        logic_differences=[],
        confidence="high" if status == "approved" else "medium",
        review_status=status,
    )


def test_missing_rc_branch_in_execute_is_reported():
    review = review_operation_equivalence(
        service_source(include_rc4=False),
        routing_plan(),
        context_plan(),
        serialization_plan(),
        forbidden=[],
    )

    assert review.review_status == "needs_revision"
    assert "StepA:RC 4" in review.missing_rc_branches


def test_approved_review_marks_operation_assembly_complete(tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task_and_artifact(conn)
    service_path = tmp_path / "Service.java"
    service_path.write_text(service_source(), encoding="utf-8")

    review = run_operation_equivalence_reviewer(conn, TASK_ID, OPERATION_ID, CHANNEL, RUN_ID, str(service_path))

    task = get_agent_task(conn, TASK_ID)
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:step_implementation:{OPERATION_ID}:{TASK_ID}")
    assert review.review_status == "approved"
    assert task["status"] == "completed"
    assert artifact["status"] == "assembly_complete"


def test_needs_revision_feeds_issues_back_to_inserter(tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task_and_artifact(conn)
    service_path = tmp_path / "Service.java"
    service_path.write_text(service_source(), encoding="utf-8")
    revisions = []
    reviews = [result("needs_revision", "StepA:RC 4"), result("approved")]

    def reviewer(java_source, routing, context, serialization):
        return reviews.pop(0)

    def revision_runner(conn, task_id, issues):
        revisions.append((task_id, issues))

    review = run_operation_equivalence_reviewer(
        conn,
        TASK_ID,
        OPERATION_ID,
        CHANNEL,
        RUN_ID,
        str(service_path),
        reviewer=reviewer,
        revision_runner=revision_runner,
    )

    assert review.review_status == "approved"
    assert revisions == [(TASK_ID, ["StepA:RC 4"])]


def test_two_revision_cycles_with_persistent_issues_escalates_to_human_review(tmp_path: Path):
    conn = memory_conn()
    store_plans(conn)
    add_task_and_artifact(conn)
    service_path = tmp_path / "Service.java"
    service_path.write_text(service_source(), encoding="utf-8")
    revisions = []

    review = run_operation_equivalence_reviewer(
        conn,
        TASK_ID,
        OPERATION_ID,
        CHANNEL,
        RUN_ID,
        str(service_path),
        reviewer=lambda java_source, routing, context, serialization: result("needs_revision", "StepA:RC 4"),
        revision_runner=lambda conn, task_id, issues: revisions.append(issues),
    )

    task = get_agent_task(conn, TASK_ID)
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:step_implementation:{OPERATION_ID}:{TASK_ID}")
    assert review.review_status == "needs_human_review"
    assert len(revisions) == 2
    assert task["status"] == "needs_human_review"
    assert task["blocking_reason"] == "equivalence_gap"
    assert artifact["status"] == "needs_human_review"


def test_human_gate3_report_counts_review_states():
    report = build_human_gate3_report(
        [result("approved"), result("needs_revision"), result("needs_human_review")],
        ["AService.java"],
    )

    assert "Operations assembled: 3" in report
    assert "Approved: 1" in report
    assert "Needs revision (pending retry): 1" in report
    assert "Needs human review: 1" in report
