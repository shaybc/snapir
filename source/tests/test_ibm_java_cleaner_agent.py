from __future__ import annotations

import subprocess
from pathlib import Path

from agents.source_conversion.ibm_java_cleaner.agent import (
    clean_ibm_java_source,
    get_conversion_task,
    request_human_review,
    run_ibm_java_cleaner_task,
    submit_cleaned_class,
)
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact


RUN_ID = "run-1"
TASK_ID = "task-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def conversion_packet(java_source: str = "class StepA {}") -> dict:
    return {
        "conversion_id": "conversion-1",
        "kind": "ibm_java",
        "channel": "INTERNET",
        "primary_source_content": java_source,
        "relationship_context": "opStep",
        "target_kind": "native_java",
    }


def add_task(conn, *, attempt_number: int = 0, max_retries: int = 3, java_source: str = "class StepA {}"):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="IbmJavaCleanerAgent",
        scope_type="java_class",
        scope_id="com.bank.StepA",
        channel="INTERNET",
        target_language="java",
        status="pending",
        attempt_number=attempt_number,
        max_retries=max_retries,
        input_data=conversion_packet(java_source),
    )


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["javac"], returncode=returncode, stdout="", stderr=stderr)


def test_ibm_import_removal_context_setter_replacement_and_return_codes_preserved():
    source = """
import com.ibm.websphere.sca.Service;
import javax.ejb.SessionBean;
import java.util.Map;
public class StepA extends CCOperationStep implements OperationStepInterface {
  public int execute() throws Exception {
    context.setValueAt("ClientId", value);
    context.getValueAt("ClientName");
    return 4;
  }
}
"""

    cleaned = clean_ibm_java_source(source)

    assert "com.ibm" not in cleaned
    assert "javax.ejb" not in cleaned
    assert "import java.util.Map;" in cleaned
    assert "ctx.setClientId(value)" in cleaned
    assert "ctx.getClientName()" in cleaned
    assert "return 4;" in cleaned
    assert "CCOperationStep" not in cleaned
    assert "OperationStepInterface" not in cleaned


def test_get_conversion_task_reads_pending_ibm_java_packet():
    conn = memory_conn()
    add_task(conn)

    packet = get_conversion_task(conn, TASK_ID)

    assert packet.kind == "ibm_java"
    assert packet.conversion_id == "conversion-1"


def test_submit_cleaned_class_records_converted_artifact(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.ibm_java_cleaner.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = submit_cleaned_class(conn, TASK_ID, "class StepA {}", str(tmp_path / "StepA.java"), RUN_ID)

    assert result == "compiled"
    assert get_agent_task(conn, TASK_ID)["status"] == "completed"
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:native_java:{TASK_ID}")
    assert artifact["status"] == "converted"
    assert artifact["compiles"] == 1


def test_compile_failure_retries_then_blocks_after_max_retries(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn, attempt_number=2, max_retries=3)
    monkeypatch.setattr(
        "agents.source_conversion.ibm_java_cleaner.agent._compile_java_source",
        lambda path: compiled(1, "compiler error"),
    )

    result = submit_cleaned_class(conn, TASK_ID, "class StepA {", str(tmp_path / "StepA.java"), RUN_ID)

    task = get_agent_task(conn, TASK_ID)
    assert result == "compile_failed"
    assert task["status"] == "blocked"
    assert task["blocking_reason"] == "compile_failed"
    assert task["attempt_number"] == 3


def test_todo_comment_requests_human_review(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.ibm_java_cleaner.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = submit_cleaned_class(conn, TASK_ID, "// TODO unknown IBM call", str(tmp_path / "StepA.java"), RUN_ID)

    task = get_agent_task(conn, TASK_ID)
    assert result == "needs_human_review"
    assert task["status"] == "needs_human_review"
    assert task["blocking_reason"] == "needs_human_mapping"


def test_mock_llm_runner_submits_cleaned_output(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn, java_source="class StepA {}")
    monkeypatch.setattr(
        "agents.source_conversion.ibm_java_cleaner.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = run_ibm_java_cleaner_task(
        conn,
        TASK_ID,
        str(tmp_path / "StepA.java"),
        RUN_ID,
        lambda packet: clean_ibm_java_source(packet.primary_source_content),
    )

    assert result == "compiled"


def test_request_human_review_sets_needs_human_mapping():
    conn = memory_conn()
    add_task(conn)

    request_human_review(conn, TASK_ID, "unknown call", ["context.magic()"])

    task = get_agent_task(conn, TASK_ID)
    assert task["status"] == "needs_human_review"
    assert task["blocking_reason"] == "needs_human_mapping"
