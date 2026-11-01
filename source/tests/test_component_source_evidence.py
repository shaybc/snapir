"""Only format/step implementations are generated; supporting Java stays complete and source-bound."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.component_identity import component_group
from runtime.component_conversion.requests import build_component_request
from test_component_graph import origin, operation, step


def test_framework_evidence_delivered_with_step_and_checked_for_freshness(tmp_path):
    originals=[origin('example.Work',['example.Context']),origin('example.Context',['example.Helper']),origin('example.Helper')]
    for record,text in originals:
        path=tmp_path/(record['fqcn'].split('.')[-1]+'.java')
        path.write_text(text,encoding='utf-8');record['source_file']=str(path)
    plan=build_component_plan({'XML/Test':operation([step()],originals)})
    targets=[node for node in plan.components.values() if node.kind=='java_implementation']
    assert [node.label for node in targets]==['example.Work']
    node=targets[0];group=component_group(plan,node.component_id)
    boundary=dict(reachable_slice=dict(nodes=[dict(source_identity=node.provenance['definition_id'],
        source_hash=node.provenance['source_hash'],kind='method',signature='example.Work.execute()')]),
        parser_checklist=dict(items=[]))
    profile=PipelineConfiguration(java_version=25,scoped_native_mode='component_first_v1')
    request,_=build_component_request(plan,group,dict(boundaries={'step-1':boundary},analysis_tool_hash='parser'),[],profile)
    supporting=[item for item in request['sources'] if item.get('role')=='supporting_source_only']
    assert {item['identity'] for item in supporting}=={'source:example.Context','source:example.Helper'}
    assert all(item['content']==Path(next(record['source_file'] for record,_ in originals
        if record['definition_id']==item['identity'])).read_text() for item in supporting)
    assert set(request['source_entry_points'])=={node.component_id}
    assert set(request['expected_contract_fields'])=={node.component_id}
    Path(originals[1][0]['source_file']).write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='source changed'):
        build_component_request(plan,group,dict(boundaries={'step-1':boundary},analysis_tool_hash='parser'),[],profile)


def test_supporting_source_cannot_be_requested_as_a_standalone_component():
    node=SimpleNamespace(kind='java_implementation',roles=['utility'])
    with pytest.raises(ValueError,match='not a standalone'):
        build_component_request(SimpleNamespace(components={'context':node}),SimpleNamespace(members=['context']),{},[],None)
