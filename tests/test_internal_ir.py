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

    out_dir = builder.persist(tmp_path / "out")
    persisted = json.loads((out_dir / "internal_ir.json").read_text(encoding="utf-8"))
    assert persisted == payload1
