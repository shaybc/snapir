from pathlib import Path
import json

from snapir.graphs import GraphBuilder


def test_graph_builder_outputs_stable_graphs_and_indexes(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "flow.xml").write_text(
        """
        <root>
          <component name='CompA' usesComponent='CompB'/>
          <component name='CompB' usesComponent='CompA'/>
          <component name='CompIsolated'/>
          <operation name='OpA' componentRef='CompA' callsOperation='OpB OpC OpD'/>
          <operation name='OpB'/>
          <operation name='OpC' callsOperation='OpD'/>
          <operation name='OpD' callsOperation='OpC'/>
          <operation name='OpLonely'/>
          <contextRead operation='OpA' context='CustomerId'/>
          <contextWrite component='CompA' contextKey='CacheKey'/>
        </root>
        """.strip(),
        encoding="utf-8",
    )

    builder = GraphBuilder(source, version="v1")
    payload1 = builder.build()
    payload2 = builder.build()
    assert payload1 == payload2

    out_dir = builder.persist(tmp_path / "out", include_adjacency_index=True)

    op_comp = json.loads((out_dir / "graph_operation_to_component.json").read_text(encoding="utf-8"))
    assert op_comp["count"] == 1
    assert op_comp["edges"][0]["source"] == "OpA"
    assert op_comp["edges"][0]["target"] == "CompA"

    comp_comp = json.loads((out_dir / "graph_component_to_component.json").read_text(encoding="utf-8"))
    assert comp_comp["count"] == 2

    context = json.loads((out_dir / "graph_context_dependencies.json").read_text(encoding="utf-8"))
    assert context["count"] == 2

    adj = json.loads((out_dir / "graph_operation_to_operation_adjacency_index.json").read_text(encoding="utf-8"))
    assert adj == {"OpA": ["OpB", "OpC", "OpD"], "OpC": ["OpD"], "OpD": ["OpC"]}

    diagnostics = json.loads((out_dir / "graph_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["summary"]["operation_cycles"] == 1
    assert diagnostics["summary"]["component_cycles"] == 1
    assert diagnostics["summary"]["unreachable_operations"] == 1
    assert diagnostics["summary"]["unreachable_components"] == 1
    assert diagnostics["issues"]["high_fanout"]["operation"][0] == {"node": "OpA", "fanout": 4}
