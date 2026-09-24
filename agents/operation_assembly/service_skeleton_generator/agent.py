from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path
from typing import Callable

from constants import AGENT_MODEL, JAVA_PACKAGE_BASE, MAX_AGENT_TASK_RETRIES, NATIVE_JAVA_ROOT, SPRING_BOOT_VERSION
from models.conversion_models import ContextPlan, RoutingPlan, SerializationPlan
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
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


SKELETON_INSTRUCTION = """
You are generating a Java Spring Boot service class skeleton.

You receive three plan objects. Generate ONLY the class structure.
Do NOT implement any method bodies. Use:
  throw new UnsupportedOperationException("not yet implemented");
for every method body.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
JAVA_PACKAGE_BASE: {java_package_base}
SPRING_BOOT_VERSION: {spring_boot_version}

ROUTING_PLAN: {routing_plan_json}
CONTEXT_PLAN: {context_plan_json}
SERIALIZATION_PLAN: {serialization_plan_json}

GENERATE:
1. Class declaration:
   @Service
   public class {OperationId}Service { ... }

2. Field declarations (constructor-injected):
   - One repository field per db_lookup in serialization_plan.db_lookups.
   - The context class field: private {ContextClass} ctx;
     (created fresh per execute call, NOT a field - see below)

3. Constructor with @Autowired dependencies.

4. Six method signatures (in this order, no bodies yet):
   a. public {ReplyDtoType} execute(String requestXml) throws Exception
   b. private {RequestDtoType} deserializeRequest(String xml)
   c. private void initializeContext({ContextClass} ctx, {RequestDtoType} req)
   d. private void enrichWithDbLookups({ContextClass} ctx)
   e. private String serializeReply({ReplyDtoType} reply)
   f. private String serializeErrorReply({ErrorReplyDtoType} err)

5. Derive DTO type names from plan:
   RequestDtoType = {OperationId}Request
   ReplyDtoType   = {OperationId}Response
   ErrorReplyDtoType = ErrorResponse  (from common-lib)
   ContextClass   = {ContextId} (from context_plan.context_class)

6. Include correct imports:
   - org.springframework.stereotype.Service
   - All DTO types
   - Repository types (from db_lookups)
   - Context class

IMPORTANT: The context class is instantiated INSIDE execute(), not as a field.
Write: var ctx = new {ContextClass}(); at the start of execute().

Output ONLY the Java source. No explanation. No markdown.
"""


def load_service_skeleton_plans(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> tuple[RoutingPlan, ContextPlan, SerializationPlan]:
    """Load the three deterministic plans required for skeleton generation."""
    routing_row = get_routing_plan(conn, operation_id, channel, run_id)
    context_row = get_context_plan(conn, operation_id, channel, run_id)
    serialization_row = get_serialization_plan(conn, operation_id, channel, run_id)
    if not routing_row or not routing_row.get("plan_json"):
        raise KeyError(f"RoutingPlan not found: {operation_id}/{channel}/{run_id}")
    if not context_row or not context_row.get("plan_json"):
        raise KeyError(f"ContextPlan not found: {operation_id}/{channel}/{run_id}")
    if not serialization_row or not serialization_row.get("plan_json"):
        raise KeyError(f"SerializationPlan not found: {operation_id}/{channel}/{run_id}")
    return (
        RoutingPlan(**routing_row["plan_json"]),
        ContextPlan(**context_row["plan_json"]),
        SerializationPlan(**serialization_row["plan_json"]),
    )


def build_service_skeleton_source(
    operation_id: str,
    channel: str,
    routing_plan: RoutingPlan,
    context_plan: ContextPlan,
    serialization_plan: SerializationPlan,
    java_package_base: str = JAVA_PACKAGE_BASE,
) -> str:
    """Build a Spring service skeleton with stubbed method bodies."""
    class_name = f"{operation_id}Service"
    request_type = f"{operation_id}Request"
    reply_type = f"{operation_id}Response"
    error_type = "ErrorResponse"
    context_type = context_plan.context_class
    repository_types = [_repository_type(lookup.field_name) for lookup in serialization_plan.db_lookups]
    imports = [
        "import org.springframework.beans.factory.annotation.Autowired;",
        "import org.springframework.stereotype.Service;",
        f"import {java_package_base}.context.{context_type};",
        f"import {java_package_base}.dto.{request_type};",
        f"import {java_package_base}.dto.{reply_type};",
        f"import {java_package_base}.dto.{error_type};",
    ]
    imports.extend(
        f"import {java_package_base}.repository.{repository_type};"
        for repository_type in repository_types
    )
    lines = [
        f"package {java_package_base}.service;",
        "",
        *imports,
        "",
        "@Service",
        f"public class {class_name} {{",
    ]
    for repository_type in repository_types:
        lines.append(f"    private final {repository_type} {_lower_first(repository_type)};")
    if repository_types:
        lines.append("")
        lines.append("    @Autowired")
        lines.append(
            f"    public {class_name}("
            + ", ".join(f"{repo} {_lower_first(repo)}" for repo in repository_types)
            + ") {"
        )
        for repository_type in repository_types:
            field_name = _lower_first(repository_type)
            lines.append(f"        this.{field_name} = {field_name};")
        lines.append("    }")
    else:
        lines.append("")
        lines.append(f"    public {class_name}() {{")
        lines.append("    }")
    lines.extend([
        "",
        f"    public {reply_type} execute(String requestXml) throws Exception {{",
        f"        var ctx = new {context_type}();",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "",
        f"    private {request_type} deserializeRequest(String xml) {{",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "",
        f"    private void initializeContext({context_type} ctx, {request_type} req) {{",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "",
        f"    private void enrichWithDbLookups({context_type} ctx) {{",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "",
        f"    private String serializeReply({reply_type} reply) {{",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "",
        f"    private String serializeErrorReply({error_type} err) {{",
        '        throw new UnsupportedOperationException("not yet implemented");',
        "    }",
        "}",
    ])
    return "\n".join(lines)


def write_and_compile_service_skeleton(
    conn: sqlite3.Connection,
    task_id: str,
    java_source: str,
    operation_id: str,
    channel: str,
    run_id: str,
    output_root: str = NATIVE_JAVA_ROOT,
) -> str:
    """Write a service skeleton to disk, compile it, and store artifact state."""
    task = get_agent_task(conn, task_id)
    output_path = Path(output_root) / channel / operation_id / "Service.java"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(java_source, encoding="utf-8")
    compile_result = _compile_java_source(output_path)
    if compile_result.returncode == 0:
        _record_native_artifact(
            conn,
            task,
            run_id,
            task_id,
            operation_id,
            str(output_path),
            status="converted",
            compiles=True,
            review_status="pending",
            attempt_number=int(task["attempt_number"]) if task else 0,
        )
        if task:
            update_task_status(conn, task_id, "completed")
        return "compiled"
    attempt_number = (int(task["attempt_number"]) + 1) if task else 1
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES) if task else MAX_AGENT_TASK_RETRIES
    status = "blocked" if attempt_number >= max_retries else "failed"
    blocking_reason = "compile_failed" if status == "blocked" else None
    if task:
        _set_task_failure(conn, task_id, status, attempt_number, compile_result.stderr, blocking_reason)
    _record_native_artifact(
        conn,
        task,
        run_id,
        task_id,
        operation_id,
        str(output_path),
        status=status,
        compiles=False,
        review_status="failed",
        review_notes=[compile_result.stderr],
        blocking_reason=blocking_reason,
        attempt_number=attempt_number,
    )
    return "compile_failed"


def run_service_skeleton_generator_task(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    generator: Callable[[RoutingPlan, ContextPlan, SerializationPlan], str] | None = None,
    output_root: str = NATIVE_JAVA_ROOT,
) -> str:
    """Load plans, generate a skeleton, write it, and compile it."""
    routing_plan, context_plan, serialization_plan = load_service_skeleton_plans(
        conn,
        operation_id,
        channel,
        run_id,
    )
    java_source = generator(routing_plan, context_plan, serialization_plan) if generator else build_service_skeleton_source(
        operation_id,
        channel,
        routing_plan,
        context_plan,
        serialization_plan,
    )
    return write_and_compile_service_skeleton(
        conn,
        task_id,
        java_source,
        operation_id,
        channel,
        run_id,
        output_root=output_root,
    )


def _repository_type(field_name: str) -> str:
    return f"{_upper_first(field_name)}Repository"


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:]


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:]


def _compile_java_source(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["javac", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def _record_native_artifact(
    conn: sqlite3.Connection,
    task: dict | None,
    run_id: str,
    task_id: str,
    operation_id: str,
    output_path: str,
    *,
    status: str,
    compiles: bool,
    review_status: str,
    review_notes: list[str] | None = None,
    blocking_reason: str | None = None,
    attempt_number: int = 0,
) -> None:
    upsert_native_java_artifact(
        conn,
        artifact_id=f"{run_id}:service_skeleton:{operation_id}:{task_id}",
        run_id=run_id,
        conversion_id=operation_id,
        kind="xml_operation",
        logical_id=operation_id,
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
    from tools.state_store_tools._json import utc_now

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
        (status, blocking_reason, attempt_number, error_message, utc_now(), task_id),
    )
    conn.commit()


service_skeleton_generator_agent = LlmAgent(
    name="ServiceSkeletonGeneratorAgent",
    description="Generates Spring Boot service class skeletons from deterministic plans.",
    model=AGENT_MODEL,
    instruction=SKELETON_INSTRUCTION,
    tools=[load_service_skeleton_plans, write_and_compile_service_skeleton],
)
