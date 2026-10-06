from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from constants import AGENT_MODEL, MAX_AGENT_TASK_RETRIES
from models.conversion_models import (
    ConversionTaskPacket,
    DbLookupRequirement,
    FieldTransformation,
    ServiceLayerRequirements,
)
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
from tools.state_store_tools.service_layer_requirements import upsert_service_layer_requirements

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


OUTPUT_MARKER = "<<<SLR_START>>>"


XML_TO_JAVA_INSTRUCTION = """
You are converting a WSBCC fmtDef XML definition into:
1. A JAXB-annotated Java DTO class (pure data carrier, NO logic)
2. A ServiceLayerRequirements JSON spec

INPUT DOCUMENTS:
FORMAT_ID: {format_id}
FMTDEF_XML: the raw fmtDef XML
STRUCTURE_SECTION: the resolved tag tree from the vault ## Structure section
  (includes decorator lines already resolved - read them directly)
SERIALIZATION_NOTES: transparent/unnamed CCXML flags
DATABASE_LOOKUPS: CCTableFormat DB lookup specifications

JAXB DTO RULES (non-negotiable):
1. The DTO is a pure data carrier. No logic. No DB calls. No validation.
2. Use @XmlRootElement(name="...") on the root element.
3. Use @XmlElement(name="...") on each field.
4. Use @XmlElementWrapper + @XmlElement on List fields (from CCIColl tags).
5. transparent="true" on a CCXML element means OMIT that wrapper element
   from the JAXB mapping - its children appear at the parent level.
6. CCTableFormat nodes: DO NOT add a field for the looked-up value in the DTO.
   Instead add it to ServiceLayerRequirements.db_lookups. The service layer
   will populate this field before serialization.
7. Field types: CCString->String, CCDate->String (formatted),
   CCBoolean->boolean, NumberFormat->String, CCIColl->List<NestedDtoType>.
8. All fields private with getters and setters.
9. Include a no-argument constructor.
10. Output the DTO class only. No imports beyond JAXB. No explanation.

SERVICE LAYER REQUIREMENTS RULES:
For each decorator chain in STRUCTURE_SECTION:
- field_name: the dataName of the formatter
- format_direction: list of addDecoration calls in forward order
- unformat_direction: list of removeDecoration calls in REVERSE order
  (last decorator first)
For each DATABASE_LOOKUP entry:
- Move to db_lookups in ServiceLayerRequirements
- The service layer must call the DB and populate this field before
  serialization; the DTO does not contain this lookup logic.

Output TWO items separated by the marker <<<SLR_START>>>:
1. The complete JAXB DTO Java source
<<<SLR_START>>>
2. The ServiceLayerRequirements as JSON
"""


@dataclass
class StructureField:
    """Formatter node extracted from a vault Structure section."""

    tag_name: str
    field_name: str
    decorators: list[str]
    transparent: bool = False


def get_format_conversion_task(conn: sqlite3.Connection, task_id: str) -> ConversionTaskPacket:
    """Read a pending fmtDef conversion task from agent_tasks."""
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    if task["status"] not in {"pending", "failed", "in_progress"}:
        raise ValueError(f"Conversion task is not runnable: {task['status']}")
    input_data = task.get("input_json") or {}
    if input_data.get("kind") != "xml_fmtdef":
        raise ValueError(f"Conversion task is not xml_fmtdef: {input_data.get('kind')}")
    return ConversionTaskPacket(**input_data)


def submit_jaxb_dto(
    conn: sqlite3.Connection,
    task_id: str,
    java_source: str,
    output_path: str,
    run_id: str,
    *,
    build_context=None,
    dependency_proposals=(),
) -> str:
    """Write a generated JAXB DTO, compile it, and update task/artifact state."""
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


def submit_service_layer_requirements(
    conn: sqlite3.Connection,
    format_id: str,
    channel: str,
    slr: ServiceLayerRequirements,
    run_id: str,
) -> None:
    """Store ServiceLayerRequirements in the state store."""
    upsert_service_layer_requirements(
        conn,
        format_id=format_id,
        channel=channel,
        run_id=run_id,
        requirements=slr.model_dump(mode="json"),
        status="ready",
    )


def parse_converter_output(output: str) -> tuple[str, ServiceLayerRequirements]:
    """Split LLM output into Java source and ServiceLayerRequirements."""
    if OUTPUT_MARKER not in output:
        raise ValueError("Converter output is missing <<<SLR_START>>> marker")
    java_source, slr_json = output.split(OUTPUT_MARKER, 1)
    return java_source.strip(), ServiceLayerRequirements(**json.loads(slr_json))


def run_xml_to_java_converter_task(
    conn: sqlite3.Connection,
    task_id: str,
    output_path: str,
    run_id: str,
    converter: Callable[[ConversionTaskPacket], str],
    *,
    build_context=None,
) -> str:
    """Run one fmtDef conversion task with an injectable converter function."""
    task = get_format_conversion_task(conn, task_id)
    try:
        output = converter(task)
        dependencies = []
        if build_context is not None:
            from models.maven_dependency import JavaConversionOutput
            payload = json.loads(output)
            slr = ServiceLayerRequirements.model_validate(payload.pop("service_layer_requirements"))
            converted = JavaConversionOutput.model_validate(payload)
            java_source, dependencies = converted.java_source, converted.dependencies
        else:
            java_source, slr = parse_converter_output(output)
    except Exception as exc:
        _record_parse_failure(conn, task_id, str(exc))
        return "parse_failed"
    submit_service_layer_requirements(conn, slr.format_id, slr.channel, slr, run_id)
    if build_context is not None:
        return submit_jaxb_dto(conn, task_id, java_source, output_path, run_id,
                               build_context=build_context, dependency_proposals=dependencies)
    return submit_jaxb_dto(conn, task_id, java_source, output_path, run_id)


def build_jaxb_dto_from_structure(format_id: str, class_name: str, structure_section: str) -> str:
    """Build a deterministic JAXB DTO from a resolved Structure section."""
    fields = [
        field for field in parse_structure_fields(structure_section)
        if not field.transparent and field.tag_name != "CCTableFormat" and field.tag_name != "CCXML"
    ]
    imports = [
        "import jakarta.xml.bind.annotation.XmlElement;",
        "import jakarta.xml.bind.annotation.XmlRootElement;",
    ]
    if any(field.tag_name == "CCIColl" for field in fields):
        imports.extend([
            "import jakarta.xml.bind.annotation.XmlElementWrapper;",
            "import java.util.List;",
        ])
    lines = [
        *imports,
        "",
        f"@XmlRootElement(name=\"{format_id}\")",
        f"public class {class_name} {{",
        f"    public {class_name}() {{",
        "    }",
        "",
    ]
    for field in fields:
        java_type = _java_type(field)
        if field.tag_name == "CCIColl":
            lines.append(f"    @XmlElementWrapper(name=\"{field.field_name}\")")
            lines.append("    @XmlElement(name=\"item\")")
        else:
            lines.append(f"    @XmlElement(name=\"{field.field_name}\")")
        lines.append(f"    private {java_type} {field.field_name};")
        lines.append("")
    for field in fields:
        java_type = _java_type(field)
        accessor_name = _upper_first(field.field_name)
        lines.extend([
            f"    public {java_type} get{accessor_name}() {{",
            f"        return {field.field_name};",
            "    }",
            "",
            f"    public void set{accessor_name}({java_type} {field.field_name}) {{",
            f"        this.{field.field_name} = {field.field_name};",
            "    }",
            "",
        ])
    lines.append("}")
    return "\n".join(lines)


def build_service_layer_requirements_from_structure(
    format_id: str,
    channel: str,
    structure_section: str,
    database_lookups: list[dict] | None = None,
) -> ServiceLayerRequirements:
    """Build ServiceLayerRequirements from decorator chains and DB lookup metadata."""
    transformations = []
    for field in parse_structure_fields(structure_section):
        if field.decorators:
            transformations.append(
                FieldTransformation(
                    field_name=field.field_name,
                    format_direction=field.decorators,
                    unformat_direction=list(reversed(field.decorators)),
                )
            )
    lookups = [
        DbLookupRequirement(**lookup)
        for lookup in (database_lookups or _database_lookups_from_structure(structure_section))
    ]
    return ServiceLayerRequirements(
        format_id=format_id,
        channel=channel,
        field_transformations=transformations,
        db_lookups=lookups,
    )


def parse_structure_fields(structure_section: str) -> list[StructureField]:
    """Extract formatter fields and decorator chains from a Structure section."""
    fields: list[StructureField] = []
    current: StructureField | None = None
    for raw_line in structure_section.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```") or line.startswith("</"):
            continue
        if line.startswith("decorator:"):
            decorator = re.search(r"decorator:\s*<([^\s/>]+)", line)
            if current and decorator:
                current.decorators.append(decorator.group(1))
            continue
        node = _structure_node(line)
        if node:
            fields.append(node)
            current = node
    return fields


def _database_lookups_from_structure(structure_section: str) -> list[dict]:
    lookups = []
    for raw_line in structure_section.splitlines():
        line = raw_line.strip()
        if not line.startswith("<CCTableFormat"):
            continue
        attrs = _attrs(line)
        field_name = attrs.get("dataName")
        if not field_name:
            continue
        lookups.append({
            "field_name": field_name,
            "from_table": attrs.get("fromTable", ""),
            "from_column": attrs.get("fromColumn", ""),
            "key_value_field": attrs.get("keyValue", ""),
        })
    return lookups


def _structure_node(line: str) -> StructureField | None:
    match = re.search(r"<([^\s/>]+)", line)
    attrs = _attrs(line)
    if not match or "dataName" not in attrs:
        return None
    return StructureField(
        tag_name=match.group(1),
        field_name=attrs["dataName"],
        decorators=[],
        transparent=attrs.get("transparent", "").lower() == "true",
    )


def _attrs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=\"([^\"]*)\"", line))


def _java_type(field: StructureField) -> str:
    if field.tag_name == "CCIColl":
        return f"List<{_upper_first(field.field_name)}Item>"
    return {
        "CCString": "String",
        "CCDate": "String",
        "CCBoolean": "boolean",
        "NumberFormat": "String",
    }.get(field.tag_name, "String")


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:]


def _compile_java_source(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["javac", str(path)],
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
        kind="xml_fmtdef",
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


def _record_parse_failure(conn: sqlite3.Connection, task_id: str, error_message: str) -> None:
    task = get_agent_task(conn, task_id)
    if task is None:
        raise KeyError(f"Conversion task not found: {task_id}")
    attempt_number = int(task["attempt_number"]) + 1
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES)
    status = "blocked" if attempt_number >= max_retries else "failed"
    blocking_reason = "compile_failed" if status == "blocked" else None
    _set_task_failure(conn, task_id, status, attempt_number, error_message, blocking_reason)


def _utc_now() -> str:
    from tools.state_store_tools._json import utc_now

    return utc_now()


xml_to_java_converter_agent = LlmAgent(
    name="XmlToJavaConverterAgent",
    description="Converts WSBCC fmtDef XML to JAXB DTOs and service layer requirements.",
    model=AGENT_MODEL,
    instruction=XML_TO_JAVA_INSTRUCTION,
    tools=[get_format_conversion_task, submit_jaxb_dto, submit_service_layer_requirements],
)
