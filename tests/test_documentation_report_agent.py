from __future__ import annotations

from agents.documentation_report.agent import (
    build_human_gate4_report,
    generate_final_report,
    generate_operation_doc,
)
from models.common_models import TargetLanguage
from models.validation_models import ValidationReport
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact
from tools.state_store_tools.trace_comparisons import insert_trace_comparison


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def validation_report(operation_id: str) -> ValidationReport:
    return ValidationReport(
        run_id=RUN_ID,
        operation_id=operation_id,
        target_language=TargetLanguage.java,
        build_passed=True,
        test_passed=True,
        xml_compat_passed=True,
        ibm_guard_passed=True,
        behavior_equiv_passed=True,
        attempt_number=1,
    )


def add_artifact(conn, operation_id: str, status: str = "validated", blocking_reason: str | None = None):
    upsert_generated_artifact(
        conn,
        artifact_id=f"artifact-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel="INTERNET",
        target_language="java",
        artifact_kind="service",
        generated_path=f"generated/{operation_id}",
        status=status,
        blocking_reason=blocking_reason,
    )


def test_per_operation_doc_contains_operation_id_heading():
    doc = generate_operation_doc(
        operation_id="TransferFunds",
        channel="INTERNET",
        operation_xml="<operation />",
        service_path="generated/TransferFunds",
        routing_plan_summary="StepA -> end",
        validation_report=validation_report("TransferFunds"),
        shared_components=[],
    )

    assert "## Operation: TransferFunds" in doc


def test_final_report_includes_all_operations(tmp_path):
    conn = memory_conn()
    add_artifact(conn, "TransferFunds")
    add_artifact(conn, "GetBalance")
    output_path = tmp_path / "final.md"

    generate_final_report(conn, RUN_ID, str(output_path))

    report = output_path.read_text(encoding="utf-8")
    assert "- TransferFunds" in report
    assert "- GetBalance" in report


def test_gate4_output_includes_routing_mismatch_count(tmp_path):
    conn = memory_conn()
    add_artifact(conn, "TransferFunds")
    insert_trace_comparison(
        conn,
        comparison_id="cmp-1",
        operation_id="TransferFunds",
        channel="INTERNET",
        run_id=RUN_ID,
        scenario="success",
        matched=False,
        failure_class="routing_mismatch",
    )

    gate = build_human_gate4_report(conn, RUN_ID, str(tmp_path / "final.md"))

    assert "Routing mismatches detected and fixed: 1" in gate
