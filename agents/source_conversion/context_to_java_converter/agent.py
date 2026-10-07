from __future__ import annotations

import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Callable

from constants import JAVA_VERSION, AGENT_MODEL, JAVA_PACKAGE_BASE, MAX_AGENT_TASK_RETRIES
from models.conversion_models import ContextField, ContextFieldInventory, ConversionTaskPacket
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
from tools.state_store_tools.context_field_inventories import get_context_field_inventory
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


CONTEXT_TO_JAVA_INSTRUCTION = """
You are generating a typed Java context class from a field inventory.

A WSBCC context is a runtime data carrier. The generated class must be a flat
plain Java class - no inheritance, no framework annotations.

CONTEXT_ID: {context_id}
CONTEXT_CHAIN: {context_chain}  (ordered leaf-first, root last)
FIELDS: {fields_json}
  Each field has: name, java_type, context_level, inherited, source

RULES:
1. One flat class. No extends. No @annotations.
2. One private field per entry in FIELDS.
   Use the java_type from the field inventory.
3. Getter and setter for every field.
   Getter: get{FieldName}(), Setter: set{FieldName}({type} value).
4. No-argument constructor.
5. Add a comment on each inherited field:
   // inherited from {context_level}
6. Package: {java_package_base}.context
7. Class name: {context_id} (use the context_id as the class name).
8. No business logic. No DB calls. No XML handling.
9. Output the Java source only. No explanation.

FIELDS:
{fields_json}
"""


def get_context_inventory(
    conn: sqlite3.Connection,
    context_id: str,
    channel: str,
    run_id: str,
) -> ContextFieldInventory:
    """Read a pre-built context field inventory from the state store."""
    row = get_context_field_inventory(conn, context_id, channel, run_id)
    if row is None or not row.get("inventory_json"):
        raise KeyError(f"Context field inventory not found: {context_id}/{channel}/{run_id}")
    return ContextFieldInventory(**row["inventory_json"])


def submit_context_class(
    conn: sqlite3.Connection,
    task_id: str,
    java_source: str,
    output_path: str,
    run_id: str,
    *,
    build_context=None,
    dependency_proposals=(),
) -> str:
    """Write a generated context class, compile it, and persist conversion status."""
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if build_context is not None:
        compile_result = build_context.submit(java_source, output_path, task_id, dependency_proposals)
    else:
        path.write_text(java_source, encoding="utf-8")
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


def run_context_to_java_converter_task(
    conn: sqlite3.Connection,
    task_id: str,
    context_id: str,
    channel: str,
    run_id: str,
    output_path: str,
    converter: Callable[[ContextFieldInventory], str],
    *,
    build_context=None,
) -> str:
    """Run one context conversion task with an injectable converter function."""
    inventory = get_context_inventory(conn, context_id, channel, run_id)
    java_source = converter(inventory)
    if build_context is not None:
        from tools.maven_dependency_tools.conversion_submission import parse_conversion_output
        converted = parse_conversion_output(java_source)
        return submit_context_class(conn, task_id, converted.java_source, output_path, run_id,
                                    build_context=build_context, dependency_proposals=converted.dependencies)
    return submit_context_class(conn, task_id, java_source, output_path, run_id)


def build_context_java_class(
    inventory: ContextFieldInventory,
    java_package_base: str = JAVA_PACKAGE_BASE,
) -> str:
    """Build a flat Java context class from an inventory."""
    class_name = sanitize_class_name(inventory.context_id)
    fields = [_java_field(field) for field in inventory.fields]
    imports = _imports_for_fields(fields)
    lines = [
        f"package {java_package_base}.context;",
        "",
        *imports,
        *("" if not imports else [""]),
        f"public class {class_name} {{",
        f"    public {class_name}() {{",
        "    }",
        "",
    ]
    for field, java_name, java_type in fields:
        if field.inherited:
            lines.append(f"    // inherited from {field.context_level}")
        lines.append(f"    private {java_type} {java_name};")
        lines.append("")
    for field, java_name, java_type in fields:
        accessor = _upper_first(java_name)
        lines.extend([
            f"    public {java_type} get{accessor}() {{",
            f"        return {java_name};",
            "    }",
            "",
            f"    public void set{accessor}({java_type} value) {{",
            f"        this.{java_name} = value;",
            "    }",
            "",
        ])
    lines.append("}")
    return "\n".join(lines)


def sanitize_java_identifier(value: str) -> str:
    """Convert an inventory field name into a valid lower-camel Java identifier."""
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        return "field"
    first = parts[0][:1].lower() + parts[0][1:]
    identifier = first + "".join(part[:1].upper() + part[1:] for part in parts[1:])
    if identifier[0].isdigit():
        identifier = f"field{identifier}"
    return identifier


def sanitize_class_name(value: str) -> str:
    """Convert a context id into a valid Java class name."""
    identifier = sanitize_java_identifier(value)
    return _upper_first(identifier)


def _java_field(field: ContextField) -> tuple[ContextField, str, str]:
    return field, sanitize_java_identifier(field.name), field.inferred_type


def _imports_for_fields(fields: list[tuple[ContextField, str, str]]) -> list[str]:
    imports = []
    java_types = {java_type for _, _, java_type in fields}
    if "LocalDate" in java_types:
        imports.append("import java.time.LocalDate;")
    if "BigDecimal" in java_types:
        imports.append("import java.math.BigDecimal;")
    if "List<Object>" in java_types:
        imports.append("import java.util.List;")
    return imports


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:]


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
        kind="xml_context",
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


def _utc_now() -> str:
    from tools.state_store_tools._json import utc_now

    return utc_now()


context_to_java_converter_agent = LlmAgent(
    name="ContextToJavaConverterAgent",
    description="Converts context field inventories to typed flat Java context classes.",
    model=AGENT_MODEL,
    instruction=CONTEXT_TO_JAVA_INSTRUCTION,
    tools=[get_context_inventory, submit_context_class],
)
