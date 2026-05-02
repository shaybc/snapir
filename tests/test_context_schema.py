from pathlib import Path
import json

from snapir.context_schema import ContextSchemaBuilder


def test_context_schema_builder_generates_deterministic_schema_and_java_metadata(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <format name='OrderFmt'>
            <field name='customer_id' type='string'/>
            <field name='createdTime'/>
            <field name='itemCount' datatype='integer'/>
            <field name='errorCode'/>
          </format>
          <contextRead field='customer_id'/>
          <contextWrite field='createdTime'/>
          <contextRead field='itemCount'/>
          <contextWrite field='itemCount'/>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    builder = ContextSchemaBuilder(source, version="v1")
    payload1 = builder.build()
    payload2 = builder.build()
    assert payload1 == payload2

    fields = payload1["context_schema"]["fields"]
    assert [f["name"] for f in fields] == ["createdTime", "customer_id", "errorCode", "itemCount"]

    created_at = next(f for f in fields if f["name"] == "createdTime")
    item_count = next(f for f in fields if f["name"] == "itemCount")
    error_code = next(f for f in fields if f["name"] == "errorCode")

    assert created_at["logical_type"] == "datetime"
    assert created_at["type_resolution_rule"] == "inferred_from_name_and_class"
    assert item_count["logical_type"] == "int"
    assert item_count["type_resolution_rule"] == "attribute_precedence:datatype"
    assert error_code["logical_type"] == "error_code"

    java_fields = payload1["java_context_metadata"]["fields"]
    assert [f["name"] for f in java_fields] == ["createdTime", "customerId", "errorCode", "itemCount"]
    assert any(f["name"] == "customerId" and "@NotNull" in f["annotation_hints"] for f in java_fields)
    assert any(f["name"] == "errorCode" and "@Pattern" in f["annotation_hints"] for f in java_fields)

    out_dir = builder.persist(tmp_path / "out")
    persisted = json.loads((out_dir / "java_context_metadata.json").read_text(encoding="utf-8"))
    assert persisted == payload1["java_context_metadata"]
