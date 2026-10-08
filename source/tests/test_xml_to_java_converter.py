from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agents.source_conversion.xml_to_java_converter.agent import (
    OUTPUT_MARKER,
    build_jaxb_dto_from_structure,
    build_service_layer_requirements_from_structure,
    get_format_conversion_task,
    parse_converter_output,
    run_xml_to_java_converter_task,
    submit_jaxb_dto,
    submit_service_layer_requirements,
)
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import get_native_java_artifact
from tools.state_store_tools.service_layer_requirements import get_service_layer_requirements


RUN_ID = "run-1"
TASK_ID = "task-xml-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def compiled(returncode: int, stderr: str = ""):
    return subprocess.CompletedProcess(args=["javac"], returncode=returncode, stdout="", stderr=stderr)


def conversion_packet() -> dict:
    return {
        "conversion_id": "RequestFmt",
        "kind": "xml_fmtdef",
        "channel": "INTERNET",
        "primary_source_content": "<fmtDef/>",
        "relationship_context": "format",
        "target_kind": "jaxb_dto",
    }


def add_task(conn, *, attempt_number: int = 0, max_retries: int = 3):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="XmlToJavaConverterAgent",
        scope_type="format",
        scope_id="RequestFmt",
        channel="INTERNET",
        target_language="java",
        status="pending",
        attempt_number=attempt_number,
        max_retries=max_retries,
        input_data=conversion_packet(),
    )


def test_transparent_ccxml_omits_wrapper_element_from_dto():
    structure = """
<CCXML dataName="TransparentWrapper" transparent="true">
  <CCString dataName="ClientId"/>
</CCXML>
"""

    dto = build_jaxb_dto_from_structure("RequestFmt", "RequestDto", structure)

    assert 'TransparentWrapper' not in dto
    assert '@XmlElement(name="ClientId")' in dto
    assert "private String ClientId;" in dto


def test_cctableformat_appears_in_slr_db_lookups_not_dto():
    structure = """
<CCXML dataName="Request">
  <CCTableFormat dataName="BranchName" fromTable="BRANCHES" fromColumn="NAME" keyValue="BranchId"/>
</CCXML>
"""

    dto = build_jaxb_dto_from_structure("RequestFmt", "RequestDto", structure)
    slr = build_service_layer_requirements_from_structure("RequestFmt", "INTERNET", structure)

    assert "BranchName" not in dto
    assert slr.db_lookups[0].field_name == "BranchName"
    assert slr.db_lookups[0].from_table == "BRANCHES"
    assert slr.db_lookups[0].from_column == "NAME"
    assert slr.db_lookups[0].key_value_field == "BranchId"


def test_ccicoll_generates_list_field_with_xml_element_wrapper():
    structure = """
<CCXML dataName="Request">
  <CCIColl dataName="Accounts"/>
</CCXML>
"""

    dto = build_jaxb_dto_from_structure("RequestFmt", "RequestDto", structure)

    assert "import java.util.List;" in dto
    assert '@XmlElementWrapper(name="Accounts")' in dto
    assert '@XmlElement(name="item")' in dto
    assert "private List<AccountsItem> Accounts;" in dto


def test_decorator_chain_in_slr_has_forward_and_reverse_order():
    structure = """
<CCXML dataName="Request">
  <CCString dataName="ClientId"/>
  decorator: <TrimDecorator/>
  decorator: <PadDecorator/>
</CCXML>
"""

    slr = build_service_layer_requirements_from_structure("RequestFmt", "INTERNET", structure)

    transformation = slr.field_transformations[0]
    assert transformation.field_name == "ClientId"
    assert transformation.format_direction == ["TrimDecorator", "PadDecorator"]
    assert transformation.unformat_direction == ["PadDecorator", "TrimDecorator"]


def test_parse_converter_output_splits_java_and_slr_json():
    slr_json = {
        "format_id": "RequestFmt",
        "channel": "INTERNET",
        "field_transformations": [],
        "db_lookups": [],
    }

    java_source, slr = parse_converter_output(f"class RequestDto {{}}\n{OUTPUT_MARKER}\n{json.dumps(slr_json)}")

    assert java_source == "class RequestDto {}"
    assert slr.format_id == "RequestFmt"


def test_get_format_conversion_task_reads_pending_xml_fmtdef_packet():
    conn = memory_conn()
    add_task(conn)

    packet = get_format_conversion_task(conn, TASK_ID)

    assert packet.kind == "xml_fmtdef"
    assert packet.conversion_id == "RequestFmt"


def test_submit_jaxb_dto_records_converted_artifact(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.xml_to_java_converter.agent._compile_java_source",
        lambda path: compiled(0),
    )

    result = submit_jaxb_dto(conn, TASK_ID, "class RequestDto {}", str(tmp_path / "RequestDto.java"), RUN_ID)

    assert result == "compiled"
    assert get_agent_task(conn, TASK_ID)["status"] == "completed"
    artifact = get_native_java_artifact(conn, f"{RUN_ID}:native_java:{TASK_ID}")
    assert artifact["kind"] == "xml_fmtdef"
    assert artifact["status"] == "converted"


def test_submit_service_layer_requirements_stores_ready_row():
    conn = memory_conn()
    slr = build_service_layer_requirements_from_structure("RequestFmt", "INTERNET", "")

    submit_service_layer_requirements(conn, "RequestFmt", "INTERNET", slr, RUN_ID)

    row = get_service_layer_requirements(conn, "RequestFmt", "INTERNET", RUN_ID)
    assert row["status"] == "ready"
    assert row["requirements_json"]["format_id"] == "RequestFmt"


def test_mock_converter_runner_stores_slr_and_dto(monkeypatch, tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    monkeypatch.setattr(
        "agents.source_conversion.xml_to_java_converter.agent._compile_java_source",
        lambda path: compiled(0),
    )
    slr = build_service_layer_requirements_from_structure("RequestFmt", "INTERNET", "")

    result = run_xml_to_java_converter_task(
        conn,
        TASK_ID,
        str(tmp_path / "RequestDto.java"),
        RUN_ID,
        lambda packet: f"class RequestDto {{}}\n{OUTPUT_MARKER}\n{slr.model_dump_json()}",
    )

    assert result == "compiled"
    row = get_service_layer_requirements(conn, "RequestFmt", "INTERNET", RUN_ID)
    assert row["requirements_json"]["format_id"] == "RequestFmt"
