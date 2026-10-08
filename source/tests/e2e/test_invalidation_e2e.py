from __future__ import annotations

from pathlib import Path

from models.conversion_models import (
    ClosureStatus,
    FormatSet,
    JavaClassRef,
    OperationClosure,
)
from tools.conversion_tools.closure_validator_tool import validate_closure
from tools.state_store_tools.generated_artifacts import get_generated_artifact, upsert_generated_artifact
from tools.state_store_tools.invalidation import cascade_invalidation, detect_hash_changes
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact, upsert_native_java_artifact
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.source_artifacts import upsert_source_artifact


RUN_ID = "run-1"
CHANNEL = "INTERNET"


def test_shared_implclass_invalidation(e2e_conn, mock_llm):
    upsert_run(e2e_conn, run_id=RUN_ID, run_mode="single_channel", run_config={"auto_rerun_impacted_operations": True})
    upsert_source_artifact(
        e2e_conn,
        artifact_id="src-GetDataSP",
        run_id=RUN_ID,
        kind="ibm_java",
        logical_id="GetDataSP",
        source_hash="hash-new",
        shared=True,
        used_by_ids=["SimpleGetOp"],
    )
    upsert_native_java_artifact(
        e2e_conn,
        artifact_id="native-GetDataSP",
        run_id=RUN_ID,
        conversion_id="GetDataSP",
        kind="ibm_java",
        logical_id="GetDataSP",
        source_hash="hash-old",
        artifact_path="GetDataSP.java",
        compiles=True,
        status="converted",
    )
    upsert_generated_artifact(
        e2e_conn,
        artifact_id="gen-SimpleGetOp",
        run_id=RUN_ID,
        operation_id="SimpleGetOp",
        channel=CHANNEL,
        target_language="java",
        artifact_kind="service",
        status="converted",
    )
    upsert_generated_artifact(
        e2e_conn,
        artifact_id="gen-BranchGetOp",
        run_id=RUN_ID,
        operation_id="BranchGetOp",
        channel=CHANNEL,
        target_language="java",
        artifact_kind="service",
        status="converted",
    )

    changes = detect_hash_changes(e2e_conn, RUN_ID)
    cascade_invalidation(e2e_conn, RUN_ID, changes)

    assert changes[0].logical_id == "GetDataSP"
    assert get_native_java_artifact(e2e_conn, "native-GetDataSP")["status"] == "needs_rerun"
    assert get_generated_artifact(e2e_conn, "gen-SimpleGetOp")["status"] == "needs_rerun"
    assert get_generated_artifact(e2e_conn, "gen-BranchGetOp")["status"] == "converted"


def test_closure_blocking_latent_routing_gap(tmp_path: Path, e2e_conn):
    java_source = tmp_path / "GapStep.java"
    java_source.write_text("public class GapStep {}", encoding="utf-8")
    closure = OperationClosure(
        operation_id="GapOp",
        channel=CHANNEL,
        run_id=RUN_ID,
        status=ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE,
        source_xml_path="GapOp.xml",
        included_opstep_ids=["GapStep"],
        routing_graph={"GapStep": {"on0Do": "end"}},
        java_classes=[
            JavaClassRef(
                fqcn="GapStep",
                source_file=str(java_source),
                has_ibm_dependency=False,
                return_codes={"8": ["not found"]},
                shared=False,
            )
        ],
        formats=FormatSet(),
        context_id="BaseCtxt",
        context_chain=["BaseCtxt"],
        source_hash_composite="hash",
    )

    validated = validate_closure(closure, e2e_conn, RUN_ID, str(tmp_path))

    assert validated.status == ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE
    assert any("Latent routing gap" in issue.detail for issue in validated.blocking_issues)
