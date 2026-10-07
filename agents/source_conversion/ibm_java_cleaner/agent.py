from __future__ import annotations

import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Callable

from constants import JAVA_VERSION, AGENT_MODEL, MAX_AGENT_TASK_RETRIES
from models.conversion_models import ConversionTaskPacket
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


IBM_CLEANER_INSTRUCTION = """
You are converting an IBM WebSphere WSBCC Java implClass to clean native Java.

You will receive:
- JAVA_SOURCE: the full Java source code to convert
- PARENT_CLASS: the FQCN of the class this extends (may be null)
- INTERFACES: list of interfaces this class implements
- IBM_IMPORTS: list of IBM-specific imports to remove
- BEHAVIOR_TYPE: one or more of: db_accessor, error_mapper, validator,
  formatter, collector, unknown

Your job is to produce clean Java that preserves EXACTLY the business logic
while removing all IBM/WAS framework dependencies.

RULES - follow all of them:
1. Remove ALL imports starting with com.ibm.*, com.ibm.dse.*, javax.ejb.*,
   javax.rmi.*, org.omg.*
2. Replace IBM context access:
   context.setValueAt("FieldName", value) -> ctx.setFieldName(value)
   context.getValueAt("FieldName")        -> ctx.getFieldName()
   Where ctx is the typed context class parameter.
3. Replace IBM connection/JDBC patterns:
   context.getConnection() -> dataSource.getConnection()
   Inject DataSource as a constructor parameter.
4. Preserve the execute() method signature: public int execute() throws Exception
5. Preserve ALL return code values EXACTLY. A return of 4 must stay 4.
6. Preserve ALL business logic inside method bodies EXACTLY.
   Do not simplify, combine, or refactor business logic.
7. Remove extends CCOperationStep / implements OperationStepInterface.
   The clean class has no IBM superclass.
8. Keep all setter methods (set{AttributeName}) - these are called by the
   assembler with XML attribute values.
9. If PARENT_CLASS contains 'FormatDecoratorHolder':
   Keep addDecoration(String s) and removeDecoration(String s) methods.
   Remove initializeFrom(Tag tag) - replace with a plain constructor or setters.
10. If PARENT_CLASS contains 'AttributeXmlFormatDecoratorImpl':
    Keep formatXmlAttributes() logic but rewrite without IBM Tag parameter.
11. If you cannot determine what an IBM call does: add a TODO comment and
    flag for human review. Do NOT guess.
12. Output ONLY the clean Java source. No explanation, no markdown.

PARENT_CLASS: {parent_class}
INTERFACES: {interfaces}
IBM_IMPORTS: {ibm_imports}
BEHAVIOR_TYPE: {behavior_types}

JAVA_SOURCE:
{java_source}
"""

MANAGED_IBM_CLEANER_INSTRUCTION = IBM_CLEANER_INSTRUCTION.replace(
    "12. Output ONLY the clean Java source. No explanation, no markdown.",
    '12. Output JSON with java_source and dependencies. Each dependency must contain '
    'group_id, artifact_id, version, scope, reason, and required_classes. '
    'Propose only dependencies needed by the converted code. Use pinned versions. '
    'Do not include Composer runtime libraries. No markdown.',
)


def get_conversion_task(conn: sqlite3.Connection, task_id: str) -> ConversionTaskPacket:
    """Read a pending IBM Java conversion task from agent_tasks."""
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    if task["status"] not in {"pending", "failed", "in_progress"}:
        raise ValueError(f"Conversion task is not runnable: {task['status']}")
    input_data = task.get("input_json") or {}
    if input_data.get("kind") != "ibm_java":
        raise ValueError(f"Conversion task is not ibm_java: {input_data.get('kind')}")
    return ConversionTaskPacket(**input_data)


def submit_cleaned_class(
    conn: sqlite3.Connection,
    task_id: str,
    cleaned_java_source: str,
    output_path: str,
    run_id: str,
    *,
    managed_pom_path: str | None = None,
    dependency_proposals=None,
    dependency_verifier=None,
    allowed_ibm_artifacts=(),
    maven_settings_path: str | None = None,
    allowed_ibm_classes=(),
) -> str:
    """Write cleaned Java, compile it, and persist conversion status."""
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    if "TODO" in cleaned_java_source:
        request_human_review(conn, task_id, "needs_human_mapping", ["TODO comment in cleaned Java"])
        return "needs_human_review"

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if managed_pom_path:
        from models.maven_dependency import JavaConversionOutput
        from tools.maven_dependency_tools.conversion_submission import submit_managed_conversion

        if dependency_verifier is None:
            raise ValueError("Managed conversion requires a trusted dependency verifier")
        try:
            compile_result = submit_managed_conversion(
                JavaConversionOutput(java_source=cleaned_java_source, dependencies=dependency_proposals or []),
                output_path, managed_pom_path, dependency_verifier,
                allowed_ibm_artifacts=allowed_ibm_artifacts, task_id=task_id,
                allowed_ibm_classes=allowed_ibm_classes,
                settings_path=maven_settings_path,
            )
        except ValueError as exc:
            request_human_review(conn, task_id, "dependency_review", [str(exc)])
            return "needs_human_review"
    else:
        path.write_text(cleaned_java_source, encoding="utf-8")
        compile_result = _compile_java_source(path)
    if compile_result.returncode == 0:
        _record_native_artifact(
            conn,
            task,
            run_id,
            task_id,
            output_path,
            status="converted",
            compiles=True,
            review_status="pending",
            attempt_number=int(task["attempt_number"]),
        )
        update_task_status(conn, task_id, "completed")
        return "compiled"

    attempt_number = int(task["attempt_number"]) + 1
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES)
    status = "blocked" if attempt_number >= max_retries else "failed"
    blocking_reason = "compile_failed" if status == "blocked" else None
    _set_task_failure(conn, task_id, status, attempt_number, compile_result.stderr, blocking_reason)
    _record_native_artifact(
        conn,
        task,
        run_id,
        task_id,
        output_path,
        status=status,
        compiles=False,
        review_status="failed",
        review_notes=[compile_result.stderr],
        blocking_reason=blocking_reason,
        attempt_number=attempt_number,
    )
    return "compile_failed"


def request_human_review(
    conn: sqlite3.Connection,
    task_id: str,
    reason: str,
    evidence: list[str],
) -> None:
    """Mark a conversion task as requiring human review."""
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    conn.execute(
        """
        UPDATE agent_tasks
        SET status = 'needs_human_review',
            blocking_reason = 'needs_human_mapping',
            output_json = ?,
            updated_at = ?
        WHERE task_id = ?
        """,
        (_json_dumps({"reason": reason, "evidence": evidence}), _utc_now(), task_id),
    )
    conn.commit()


def run_ibm_java_cleaner_task(
    conn: sqlite3.Connection,
    task_id: str,
    output_path: str,
    run_id: str,
    llm_cleaner: Callable[[ConversionTaskPacket], str],
    *,
    managed_pom_path: str | None = None,
    dependency_verifier=None,
    allowed_ibm_artifacts=(),
    maven_settings_path: str | None = None,
    build_context=None,
) -> str:
    """Run one cleaner task with an injectable cleaner function for tests."""
    task = get_conversion_task(conn, task_id)
    cleaned_source = llm_cleaner(task)
    if build_context is not None:
        managed_pom_path = build_context.pom_path
        dependency_verifier = build_context.verifier
        allowed_ibm_artifacts = build_context.allowed_ibm_artifacts
        maven_settings_path = getattr(build_context.verifier, "settings_path", None)
    if managed_pom_path:
        from tools.maven_dependency_tools.conversion_submission import parse_conversion_output

        converted = parse_conversion_output(cleaned_source)
        return submit_cleaned_class(
            conn, task_id, converted.java_source, output_path, run_id,
            managed_pom_path=managed_pom_path, dependency_proposals=converted.dependencies,
            dependency_verifier=dependency_verifier, allowed_ibm_artifacts=allowed_ibm_artifacts,
            maven_settings_path=maven_settings_path,
            allowed_ibm_classes=build_context.allowed_ibm_classes if build_context else (),
        )
    return submit_cleaned_class(conn, task_id, cleaned_source, output_path, run_id)


def clean_ibm_java_source(java_source: str) -> str:
    """Apply a deterministic IBM-removal pass useful for tests and fallback cleanup."""
    cleaned_lines = [
        line
        for line in java_source.splitlines()
        if not _is_forbidden_import(line)
    ]
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(
        r"context\.setValueAt\(\"([A-Za-z0-9_]+)\"\s*,\s*([^)]+)\)",
        lambda match: f"ctx.set{match.group(1)}({match.group(2).strip()})",
        cleaned,
    )
    cleaned = re.sub(
        r"context\.getValueAt\(\"([A-Za-z0-9_]+)\"\)",
        lambda match: f"ctx.get{match.group(1)}()",
        cleaned,
    )
    cleaned = cleaned.replace("context.getConnection()", "dataSource.getConnection()")
    cleaned = re.sub(r"\s+extends\s+CCOperationStep", "", cleaned)
    cleaned = re.sub(r"\s+implements\s+OperationStepInterface", "", cleaned)
    return cleaned


def _compile_java_source(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["javac", "--release", JAVA_VERSION, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def _record_native_artifact(
    conn: sqlite3.Connection,
    task: dict,
    run_id: str,
    task_id: str,
    output_path: str,
    *,
    status: str,
    compiles: bool,
    review_status: str,
    review_notes: list[str] | None = None,
    blocking_reason: str | None = None,
    attempt_number: int = 0,
) -> None:
    input_data = task.get("input_json") or {}
    upsert_native_java_artifact(
        conn,
        artifact_id=f"{run_id}:native_java:{task_id}",
        run_id=run_id,
        conversion_id=input_data.get("conversion_id", task_id),
        kind="ibm_java",
        logical_id=input_data.get("conversion_id", task_id),
        artifact_path=output_path,
        compiles=compiles,
        review_status=review_status,
        review_notes=review_notes or [],
        status=status,
        blocking_reason=blocking_reason,
        attempt_number=attempt_number,
    )


def _set_task_failure(
    conn: sqlite3.Connection,
    task_id: str,
    status: str,
    attempt_number: int,
    error_message: str,
    blocking_reason: str | None,
) -> None:
    conn.execute(
        """
        UPDATE agent_tasks
        SET status = ?,
            blocking_reason = ?,
            attempt_number = ?,
            error_message = ?,
            updated_at = ?
        WHERE task_id = ?
        """,
        (status, blocking_reason, attempt_number, error_message, _utc_now(), task_id),
    )
    conn.commit()


def _is_forbidden_import(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(
        (
            "import com.ibm.",
            "import javax.ejb.",
            "import javax.rmi.",
            "import org.omg.",
        )
    )


def _json_dumps(value: dict) -> str:
    from tools.state_store_tools._json import dumps

    return dumps(value)


def _utc_now() -> str:
    from tools.state_store_tools._json import utc_now

    return utc_now()


ibm_java_cleaner_agent = LlmAgent(
    name="IbmJavaCleanerAgent",
    description="Converts IBM Java implClass source to clean native Java.",
    model=AGENT_MODEL,
    instruction=IBM_CLEANER_INSTRUCTION,
    tools=[get_conversion_task, submit_cleaned_class, request_human_review],
)
