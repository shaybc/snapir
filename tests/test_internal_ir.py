from pathlib import Path
import json

from snapir.internal_ir import InternalIRBuilder


def test_internal_ir_builder_is_deterministic_and_captures_contracts(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <component name='Lookup' usesComponent='Cache'/>
          <component name='Cache'/>
          <operation name='Fetch' componentRef='Lookup' callsOperation='Normalize'/>
          <operation name='Normalize'/>
          <contextRead operation='Fetch' context='customerId'/>
          <contextWrite operation='Normalize' context='resultCode'/>
          <format name='Fmt'>
            <field name='customerId'/>
            <field name='resultCode'/>
          </format>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    builder = InternalIRBuilder(source, version="v1")
    payload1 = builder.build()
    payload2 = builder.build()
    assert payload1 == payload2

    assert [x["name"] for x in payload1["signatures"]["operations"]] == ["Fetch", "Normalize"]
    assert payload1["data_flow"]["operation_calls"] == [{"from": "Fetch", "to": "Normalize"}]
    assert payload1["data_flow"]["operation_component_usage"] == [{"from": "Fetch", "to": "Lookup"}]

    effects = payload1["side_effects"]
    assert any(e["actor"] == "Fetch" and e["effect"] == "context_read" for e in effects)
    assert any(e["actor"] == "Normalize" and e["effect"] == "context_write" for e in effects)

    contracts = payload1["dependency_contracts"]["field_classification"]
    assert contracts["customerId"] == "INPUT"
    assert contracts["resultCode"] == "OUTPUT"

    plan = payload1["shared_component_conversion_plan"]
    assert plan["ordered_components"] == [
        {"name": "Cache", "reuse_score": 1},
        {"name": "Lookup", "reuse_score": 2},
    ]
    assert plan["constraints"]["blocked_cycles"] == []

    op_ir = payload1["operation_ir"]
    assert op_ir["schema_version"] == "1"
    assert [s["id"] for s in op_ir["step_graph"]["steps"]] == ["Fetch", "Normalize"]
    assert op_ir["step_graph"]["transitions"] == [{"from": "Fetch", "type": "next", "to": ["Normalize"]}]

    out_dir = builder.persist(tmp_path / "out")
    persisted = json.loads((out_dir / "internal_ir.json").read_text(encoding="utf-8"))
    assert persisted == payload1


def test_component_conversion_plan_detects_cycles_and_keeps_topological_order(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <component name='Core'/>
          <component name='Helper' usesComponent='Core'/>
          <component name='CycleA' usesComponent='CycleB'/>
          <component name='CycleB' usesComponent='CycleA'/>
          <operation name='Op1' componentRef='Helper'/>
          <operation name='Op2' componentRef='Helper'/>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    payload = InternalIRBuilder(source, version="v1").build()
    plan = payload["shared_component_conversion_plan"]

    assert [c["name"] for c in plan["ordered_components"]] == ["Core", "Helper"]
    assert plan["reuse_scores"]["Helper"] > plan["reuse_scores"]["Core"]
    assert plan["constraints"]["blocked_cycles"] == ["CycleA", "CycleB"]


def test_operation_ir_captures_branching_transformations_error_handlers_and_external_calls(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <operation name='Start' callsOperation='RouteA RouteB' mapRule='fmt:v1' onError='Recover' endpoint='https://api.example.test/v1'/>
          <operation name='RouteA' normalize='trim'/>
          <operation name='RouteB' transform='enrich'/>
          <operation name='Recover' service='dead-letter'/>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    payload = InternalIRBuilder(source, version="v1").build()
    op_ir = payload["operation_ir"]

    assert op_ir["routing"]["branches"] == [{"from": "Start", "type": "branch", "to": ["RouteA", "RouteB"]}]
    start_step = next(step for step in op_ir["step_graph"]["steps"] if step["id"] == "Start")
    assert start_step["transformations"] == [{"attribute": "mapRule", "value": "fmt:v1"}]
    assert start_step["error_handlers"] == [{"attribute": "onError", "value": "Recover"}]
    assert start_step["external_calls"] == ["https://api.example.test/v1"]
    assert {x["operation"] for x in op_ir["external_calls"]} == {"Recover", "Start"}
