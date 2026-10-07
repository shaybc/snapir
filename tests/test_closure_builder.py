from __future__ import annotations

from pathlib import Path

import pytest

from models.conversion_models import ClosureStatus
from tools.conversion_tools.closure_builder_tool import (
    build_closures_for_batch,
    build_operation_closure,
)
from tools.conversion_tools.closure_validator_tool import (
    ClosureNotReadyError,
    assert_closure_ready,
)
from tools.state_store_tools.context_field_inventories import upsert_context_field_inventory
from tools.state_store_tools.context_hierarchies import upsert_context_hierarchy
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.source_artifacts import upsert_source_artifact
from tools.state_store_tools.tag_registry import upsert_tag


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def add_ready_fixture(tmp_path: Path, return_codes: dict | None = None, transitions: dict | None = None):
    conn = memory_conn()
    composer_root = tmp_path / "composer"
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    fqcn = "com.bank.ops.StepA"
    source = composer_root / "com" / "bank" / "ops" / "StepA.java"
    source.parent.mkdir(parents=True)
    source.write_text("package com.bank.ops; public class StepA {}", encoding="utf-8")
    format_note = vault_root / "RequestFmt.md"
    format_note.write_text("## Structure\n<CCString dataName=\"ClientId\"/>\n", encoding="utf-8")
    upsert_tag(conn, tag_name="CCString", fqcn="com.bank.CCString", run_id=RUN_ID)
    upsert_context_hierarchy(conn, context_id="ContextA", run_id=RUN_ID, chain=["ContextA"], root_id="ContextA")
    upsert_context_field_inventory(
        conn,
        context_id="ContextA",
        channel="INTERNET",
        run_id=RUN_ID,
        full_chain=["ContextA"],
        inventory={"context_id": "ContextA", "channel": "INTERNET", "full_chain": ["ContextA"], "fields": []},
        status="ready",
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:operation:OpA",
        run_id=RUN_ID,
        kind="operation",
        logical_id="OpA",
        source_hash="hash-op",
        metadata={
            "id": "OpA",
            "source_file": "ops/OpA.xml",
            "operation_context": "ContextA",
            "steps": ["StepA"],
            "ref_formats": {"csRequestFormat": "RequestFmt"},
        },
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:StepA",
        run_id=RUN_ID,
        kind="opStep",
        logical_id="StepA",
        source_hash="hash-step",
        metadata={
            "id": "StepA",
            "impl_class": fqcn,
            "transitions": transitions or {"on0Do": "end"},
            "return_body_switches": {},
        },
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:format:RequestFmt",
        run_id=RUN_ID,
        kind="format",
        logical_id="RequestFmt",
        source_path=str(format_note),
        source_hash="hash-format",
        metadata={"id": "RequestFmt"},
    )
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:java_class:{fqcn}",
        run_id=RUN_ID,
        kind="java_class",
        logical_id=fqcn,
        source_hash="hash-java",
        metadata={
            "fqcn": fqcn,
            "has_ibm_dependency": False,
            "return_codes": return_codes or {"0": ["success"]},
        },
    )
    return conn, composer_root, vault_root


def test_ready_closure_passes_all_checks(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)

    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    assert closure.status == ClosureStatus.READY
    assert closure.blocking_issues == []


def test_check_1_failure_missing_java_class_ref(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)
    conn.execute("DELETE FROM source_artifacts WHERE kind = 'java_class'")
    conn.commit()

    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    assert closure.status == ClosureStatus.BLOCKED_MISSING_IMPL_CLASS


def test_check_6_failure_context_cycle_blocks_closure(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)
    upsert_context_hierarchy(
        conn,
        context_id="ContextA",
        run_id=RUN_ID,
        chain=["ContextA", "ContextB"],
        root_id="ContextB",
        has_cycle=True,
    )

    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    assert closure.status == ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE


def test_check_7_failure_return_body_switch_requires_error_format(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)
    opstep = conn.execute(
        "SELECT metadata_json FROM source_artifacts WHERE logical_id = 'StepA'"
    ).fetchone()
    metadata = __import__("json").loads(opstep["metadata_json"])
    metadata["return_body_switches"] = {"4": "ErrorFmt"}
    conn.execute(
        "UPDATE source_artifacts SET metadata_json = ? WHERE logical_id = 'StepA'",
        (__import__("json").dumps(metadata),),
    )
    conn.commit()

    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    assert closure.status == ClosureStatus.BLOCKED_MISSING_FORMAT


def test_check_10_failure_detects_latent_routing_gap(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(
        tmp_path,
        return_codes={"0": ["success"], "8": ["db error"]},
        transitions={"on0Do": "end"},
    )

    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    assert closure.status == ClosureStatus.BLOCKED_UNRESOLVED_REFERENCE
    assert "Latent routing gap" in closure.blocking_issues[0].detail


def test_build_closures_for_batch_logs_summary(tmp_path: Path, caplog):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)

    with caplog.at_level("INFO"):
        closures = build_closures_for_batch(
            conn,
            ["OpA"],
            "INTERNET",
            RUN_ID,
            str(composer_root),
            str(vault_root),
        )

    assert closures[0].status == ClosureStatus.READY
    assert "Closure batch complete" in caplog.text


def test_assert_closure_ready_raises_for_blocked_status(tmp_path: Path):
    conn, composer_root, vault_root = add_ready_fixture(tmp_path, return_codes={"8": ["db error"]}, transitions={})
    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))

    with pytest.raises(ClosureNotReadyError):
        assert_closure_ready(closure)


def test_shared_implementation_covers_each_step_and_checks_each_route(tmp_path):
    import json
    conn, composer_root, vault_root = add_ready_fixture(tmp_path)
    metadata = json.loads(conn.execute("SELECT metadata_json FROM source_artifacts WHERE logical_id='OpA'").fetchone()[0])
    metadata["steps"].append("StepB")
    conn.execute("UPDATE source_artifacts SET metadata_json=? WHERE logical_id='OpA'", (json.dumps(metadata),))
    upsert_source_artifact(conn, artifact_id="run-1:opStep:StepB", run_id=RUN_ID, kind="opStep", logical_id="StepB",
        source_hash="second-step", metadata=dict(id="StepB", impl_class="com.bank.ops.StepA", transitions={"on0Do": "end"}))
    conn.commit()
    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))
    assert closure.status == ClosureStatus.READY
    assert len(closure.java_classes) == 1
    conn.execute("UPDATE source_artifacts SET metadata_json=? WHERE logical_id='StepB'",
                 (json.dumps(dict(id="StepB", impl_class="com.bank.ops.StepA", transitions={})),))
    conn.commit()
    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))
    assert any(issue.entity_id == "StepB" and "Latent routing gap" in issue.detail for issue in closure.blocking_issues)


def test_revalidating_closure_does_not_duplicate_findings(tmp_path):
    from tools.conversion_tools.closure_validator_tool import validate_closure
    conn, composer_root, vault_root = add_ready_fixture(tmp_path, return_codes={"8": ["error"]})
    closure = build_operation_closure(conn, "OpA", "INTERNET", RUN_ID, str(composer_root), str(vault_root))
    again = validate_closure(closure, conn, RUN_ID, str(composer_root))
    assert again.blocking_issues == closure.blocking_issues
