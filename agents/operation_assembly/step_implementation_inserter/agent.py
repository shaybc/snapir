from __future__ import annotations

import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from constants import AGENT_MODEL, FORBIDDEN_DEPENDENCIES, MAX_AGENT_TASK_RETRIES
from models.conversion_models import ContextPlan, RoutingPlan, SerializationPlan
from tools.state_store_tools.agent_tasks import get_agent_task
from tools.state_store_tools.context_plans import get_context_plan
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
from tools.state_store_tools.routing_plans import get_routing_plan
from tools.state_store_tools.serialization_plans import get_serialization_plan

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


IMPLEMENTATION_PASS_INSTRUCTION = """
You are implementing ONE method body in an existing Java service class.

OPERATION_ID: {operation_id}
METHOD_TO_IMPLEMENT: {method_name}
CURRENT_CLASS: {current_skeleton_with_previously_filled_methods}

PLAN:
{plan_section_json}

SUPPORTING_SOURCE:
{supporting_source_content}

RULES:
- Implement ONLY {method_name}. Do not modify any other method.
- Replace ONLY the 'throw new UnsupportedOperationException(...)' in {method_name}.
- Keep all other method stubs unchanged.
- Output the COMPLETE class with {method_name} implemented and all other stubs intact.
- No explanation. No markdown.
"""


@dataclass(frozen=True)
class ImplementationPass:
    """One method implementation pass."""

    pass_number: int
    method_name: str
    plan_kind: str


PASSES = [
    ImplementationPass(1, "deserializeRequest", "request_parsing"),
    ImplementationPass(2, "initializeContext", "init_sequence"),
    ImplementationPass(3, "execute", "routing_steps"),
    ImplementationPass(4, "enrichWithDbLookups", "db_lookups"),
    ImplementationPass(5, "serializeReply", "response_building"),
    ImplementationPass(6, "serializeErrorReply", "error_response_building"),
]


def run_ibm_guard(java_source: str, forbidden: list[str]) -> list[str]:
    """Return forbidden dependency patterns found in Java source."""
    return [pattern for pattern in forbidden if pattern in java_source]


def replace_method_body(java_source: str, method_name: str, body_lines: list[str]) -> str:
    """Replace exactly one Java method body with the supplied body lines."""
    signature_index = java_source.find(f" {method_name}(")
    if signature_index == -1:
        raise ValueError(f"Method not found: {method_name}")
    open_brace = java_source.find("{", signature_index)
    if open_brace == -1:
        raise ValueError(f"Method body not found: {method_name}")
    close_brace = _matching_brace(java_source, open_brace)
    if close_brace is None:
        raise ValueError(f"Method body is unbalanced: {method_name}")
    body = "\n".join(f"        {line}" for line in body_lines)
    return f"{java_source[:open_brace + 1]}\n{body}\n    {java_source[close_brace:]}"


def build_execute_body(routing_plan: RoutingPlan) -> list[str]:
    """Build a deterministic routing-oriented execute body for fallback/tests."""
    lines = ["// generated routing skeleton"]
    for step in routing_plan.steps:
        method_name = _step_method_name(step.impl_class or step.step_id)
        variable_name = f"rc{step.step_index}"
        lines.append(f"int {variable_name} = {method_name}(ctx);")
        for rc, target in step.transitions.items():
            if rc.isdigit() or (rc.startswith("-") and rc[1:].isdigit()):
                lines.append(f"if ({variable_name} == {rc}) {{")
                lines.append(f"    // route to {target}")
                if target == "end":
                    lines.append("    return null;")
                lines.append("}")
            elif rc == "other":
                lines.append("else {")
                lines.append(f"    // route to {target}")
                lines.append("}")
    lines.append("throw new UnsupportedOperationException(\"not yet implemented\");")
    return lines


def run_step_implementation_inserter(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    service_path: str,
    pass_generator: Callable[[ImplementationPass, str, RoutingPlan, ContextPlan, SerializationPlan, str | None], str],
    forbidden: list[str] | None = None,
) -> str:
    """Run all six implementation passes, compiling after each successful pass."""
    routing_plan, context_plan, serialization_plan = _load_plans(conn, operation_id, channel, run_id)
    path = Path(service_path)
    current_class = path.read_text(encoding="utf-8")
    task = get_agent_task(conn, task_id)
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES) if task else MAX_AGENT_TASK_RETRIES
    for implementation_pass in PASSES:
        status, current_class = _run_single_pass(
            implementation_pass,
            current_class,
            routing_plan,
            context_plan,
            serialization_plan,
            pass_generator,
            path,
            max_retries,
        )
        if status != "compiled":
            _mark_task_compile_failure(conn, task_id, max_retries, status)
            _record_artifact(conn, task, run_id, task_id, operation_id, str(path), status="failed", compiles=False)
            return status
    guard_findings = run_ibm_guard(current_class, forbidden or FORBIDDEN_DEPENDENCIES)
    if guard_findings:
        retry_status, current_class = _retry_execute_for_guard(
            current_class,
            routing_plan,
            context_plan,
            serialization_plan,
            pass_generator,
            path,
            max_retries,
            ", ".join(guard_findings),
        )
        if retry_status != "compiled":
            _mark_task_compile_failure(conn, task_id, max_retries, retry_status)
            _record_artifact(conn, task, run_id, task_id, operation_id, str(path), status="failed", compiles=False)
            return retry_status
    _record_artifact(conn, task, run_id, task_id, operation_id, str(path), status="converted", compiles=True)
    _mark_task_completed(conn, task_id)
    return "compiled"


def _run_single_pass(
    implementation_pass: ImplementationPass,
    current_class: str,
    routing_plan: RoutingPlan,
    context_plan: ContextPlan,
    serialization_plan: SerializationPlan,
    pass_generator: Callable[[ImplementationPass, str, RoutingPlan, ContextPlan, SerializationPlan, str | None], str],
    path: Path,
    max_retries: int,
    compiler_error: str | None = None,
) -> tuple[str, str]:
    for _ in range(max_retries):
        updated_class = pass_generator(
            implementation_pass,
            current_class,
            routing_plan,
            context_plan,
            serialization_plan,
            compiler_error,
        )
        path.write_text(updated_class, encoding="utf-8")
        compile_result = _compile_java_source(path)
        if compile_result.returncode == 0:
            return "compiled", updated_class
        compiler_error = compile_result.stderr
    return "compile_failed", current_class


def _retry_execute_for_guard(
    current_class: str,
    routing_plan: RoutingPlan,
    context_plan: ContextPlan,
    serialization_plan: SerializationPlan,
    pass_generator: Callable[[ImplementationPass, str, RoutingPlan, ContextPlan, SerializationPlan, str | None], str],
    path: Path,
    max_retries: int,
    guard_error: str,
) -> tuple[str, str]:
    execute_pass = PASSES[2]
    return _run_single_pass(
        execute_pass,
        current_class,
        routing_plan,
        context_plan,
        serialization_plan,
        pass_generator,
        path,
        max_retries,
        compiler_error=f"IBM dependency guard found: {guard_error}",
    )


def _load_plans(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> tuple[RoutingPlan, ContextPlan, SerializationPlan]:
    routing = get_routing_plan(conn, operation_id, channel, run_id)
    context = get_context_plan(conn, operation_id, channel, run_id)
    serialization = get_serialization_plan(conn, operation_id, channel, run_id)
    if not routing or not routing.get("plan_json"):
        raise KeyError("RoutingPlan not found")
    if not context or not context.get("plan_json"):
        raise KeyError("ContextPlan not found")
    if not serialization or not serialization.get("plan_json"):
        raise KeyError("SerializationPlan not found")
    return (
        RoutingPlan(**routing["plan_json"]),
        ContextPlan(**context["plan_json"]),
        SerializationPlan(**serialization["plan_json"]),
    )


def _matching_brace(source: str, open_brace: int) -> int | None:
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _step_method_name(impl_class: str) -> str:
    simple_name = impl_class.rsplit(".", 1)[-1]
    return simple_name[:1].lower() + simple_name[1:]


def _compile_java_source(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["javac", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def _record_artifact(
    conn: sqlite3.Connection,
    task: dict | None,
    run_id: str,
    task_id: str,
    operation_id: str,
    service_path: str,
    *,
    status: str,
    compiles: bool,
) -> None:
    upsert_native_java_artifact(
        conn,
        artifact_id=f"{run_id}:step_implementation:{operation_id}:{task_id}",
        run_id=run_id,
        conversion_id=operation_id,
        kind="xml_operation",
        logical_id=operation_id,
        artifact_path=service_path,
        compiles=compiles,
        review_status="pending" if compiles else "failed",
        status=status,
        blocking_reason=None if compiles else "compile_failed",
        attempt_number=int(task["attempt_number"]) if task else 0,
    )


def _mark_task_completed(conn: sqlite3.Connection, task_id: str) -> None:
    from tools.state_store_tools.agent_tasks import update_task_status

    update_task_status(conn, task_id, "completed")


def _mark_task_compile_failure(conn: sqlite3.Connection, task_id: str, attempt_number: int, error_message: str) -> None:
    from tools.state_store_tools._json import utc_now

    conn.execute(
        """
        UPDATE agent_tasks
        SET status = 'blocked',
            blocking_reason = 'compile_failed',
            attempt_number = ?,
            error_message = ?,
            updated_at = ?
        WHERE task_id = ?
        """,
        (attempt_number, error_message, utc_now(), task_id),
    )
    conn.commit()


step_implementation_inserter_agent = LlmAgent(
    name="StepImplementationInserterAgent",
    description="Fills Spring service skeleton method bodies one independently compilable pass at a time.",
    model=AGENT_MODEL,
    instruction=IMPLEMENTATION_PASS_INSTRUCTION,
    tools=[run_ibm_guard],
)
