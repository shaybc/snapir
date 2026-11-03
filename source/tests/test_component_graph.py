"""CF1 plans dependencies without changing configured units or enabling generation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from models.component_conversion_plan import ComponentConversionPlan
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def origin(name,dependencies=(),text=None):
    text=text or 'package example; public class '+name.rsplit('.',1)[-1]+' {}'
    return dict(fqcn=name,status='verified_source',definition_id='source:'+name,source_hash=hashlib.sha256(text.encode()).hexdigest(),
        source_file='original/'+name.replace('.','/')+'.java',required_classes=list(dependencies)),text


def step(identity='step-1',value='first',implementation='example.Work'):
    return dict(unit_id=identity,logical_id='Repeat',kind='configured_step',fingerprint=digest([identity,value]),
        operation_identity='qualified-operation',source_definition_id=identity,occurrence_id=identity,
        effective_configuration=dict(attributes={'implClass':implementation,'value':value} if implementation else {'value':value},
                                     routes={'on0Do':'next-occurrence','onOtherDo':None}),
        configuration_xml='<opStep/>',sources=[],referenced_definitions=[],operation_calls=[])


def operation(units,originals,external=()):
    records=[item[0] for item in originals]
    sources=[dict(identity=item['definition_id'],content_hash=item['source_hash'],content=text)
             for item,text in originals if item['status']=='verified_source']
    for unit in units: unit['sources']=deepcopy(sources)
    return dict(status='prepared',units=units,behavior_request=dict(java_origins=records,external_dependencies=list(external)))


def format_node(tag,identity,implementation=None,**changes):
    return dict(tag=tag,occurrence_id=identity,definition_id=identity,source_selector='/XML/'+identity,
        attributes={'id':identity},collection_kind='keyed',java_class=implementation,decorators=[],children=[],**changes)


def assert_order(plan):
    positions={member:index for index,group in enumerate(plan.groups) for member in group.members}
    assert set(positions)==set(plan.components)
    for key,node in plan.components.items():
        for target in node.dependencies:
            assert target in plan.components and positions[target]<=positions[key]


def test_one_step_closure_orders_helpers_and_keeps_occurrences_separate():
    work=origin('example.Work',['example.Base','example.Helper'])
    originals=[work,origin('example.Helper',['example.Base']),origin('example.Base')]
    units=[step(),step('step-2','second')]
    item=operation(units,originals)
    item['behavior_request']['java_origins'].append(deepcopy(work[0]))
    unrelated,_=origin('example.Unrelated',['missing.Other']);item['behavior_request']['java_origins'].append(unrelated)
    before=deepcopy(item)
    plan=build_component_plan({'SME/Flow':item})
    assert item==before and plan.status=='planned'
    assert len(plan.unit_roots)==2 and len(set(plan.unit_roots.values()))==2
    java=[node for node in plan.components.values() if node.kind=='java_implementation']
    assert {node.label for node in java}=={'example.Work'}
    assert {source['fqcn'] for source in java[0].provenance['supporting_sources']}=={'example.Helper','example.Base'}
    assert all(node.unit_ids==['step-1','step-2'] for node in java)
    assert plan.components[plan.unit_roots['step-1']].configuration['attributes']['value']=='first'
    assert plan.components[plan.unit_roots['step-2']].configuration['routes']==units[1]['effective_configuration']['routes']
    assert_order(plan)
    item['units'].reverse();item['behavior_request']['java_origins'].reverse()
    assert build_component_plan({'SME/Flow':item})==plan
    assert not plan.generation_enabled and not plan.acceptance_gate_enabled


@pytest.mark.parametrize('self_cycle',[False,True])
def test_cycles_stay_in_deterministic_coordinated_groups(self_cycle):
    originals=[origin('example.Work',['example.Work'] if self_cycle else ['example.Helper'])]
    if not self_cycle: originals.append(origin('example.Helper',['example.Work']))
    plan=build_component_plan({'XML/Flow':operation([step()],originals)})
    cycles=[group for group in plan.groups if group.cyclic]
    assert plan.status=='planned' and len(cycles)==1 and len(cycles[0].members)==1
    assert cycles[0].wave==1 and 'stay together' in cycles[0].reason
    assert_order(plan)


def test_transitive_source_override_changes_parent_identity_without_merging_occurrences():
    first=operation([step('one')],[origin('example.Work',['example.Helper']),origin('example.Helper',text='original helper')])
    second=operation([step('two')],[origin('example.Work',['example.Helper']),origin('example.Helper',text='local override')])
    plan=build_component_plan({'XML/A':first,'SME/B':second})
    assert len([node for node in plan.components.values() if node.label=='example.Work'])==2
    helpers=[source for node in plan.components.values() for source in node.provenance.get('supporting_sources',[])
             if node.kind=='java_implementation' and source['fqcn']=='example.Helper']
    assert len(helpers)==2 and helpers[0]['source_hash']!=helpers[1]['source_hash']
    assert plan.status=='planned'


def test_uncertain_origins_preserve_all_candidates_and_prerequisites():
    item=operation([step()],[origin('example.Work',['example.Helper']),origin('example.Helper')])
    other,_=origin('example.Work',['example.Other'],'competing implementation')
    extra=origin('example.Other')
    item['behavior_request']['java_origins'].extend([other,extra[0]])
    item['units'][0]['sources'].append(dict(identity=extra[0]['definition_id'],content_hash=extra[0]['source_hash'],content=extra[1]))
    plan=build_component_plan({'XML/Flow':item})
    competing=next(node for node in plan.components.values() if node.label=='example.Work')
    assert competing.kind=='unresolved_dependency' and len(competing.provenance['candidates'])==2
    assert {source['fqcn'] for source in competing.provenance['supporting_sources']}=={'example.Helper','example.Other'}
    assert plan.status=='incomplete'
    root=plan.unit_roots['step-1']
    assert next(group for group in plan.groups if root in group.members).wave is None


def test_missing_dependencies_and_missing_source_proof_are_not_silently_dropped():
    item=operation([step()],[origin('example.Work',['missing.Helper'])]);item['units'][0]['sources']=[]
    plan=build_component_plan({'XML/Flow':item})
    assert plan.status=='incomplete' and len(plan.issues)>=2
    assert any(node.label=='missing.Helper' and node.status=='unresolved' for node in plan.components.values())
    assert all(group.wave is None for group in plan.groups)
    assert_order(plan)


def test_default_channel_mapping_and_explicit_external_policy_are_retained():
    item=operation([step(implementation=None)],[origin('example.Work',['external.Service'])],
        external=[dict(class_name='external.Service',treatment='retain',maven_coordinates='example:service:1')])
    plan=build_component_plan({'SME/Flow':item},step_mappings={'SME/Flow':'example.Work'})
    assert plan.status=='planned'
    assert next(node for node in plan.components.values() if node.label=='external.Service').status=='external_recorded'
    root=plan.components[plan.unit_roots['step-1']]
    assert root.provenance['resolved_implementation']=='example.Work' and 'implClass' not in root.configuration['attributes']
    assert build_component_plan({'SME/Flow':item}).status=='incomplete'


def test_format_children_decorators_references_and_collection_semantics_stay_ordered():
    child1=format_node('CCString','first','example.String')
    child1['decorators']=[dict(java_class='example.Decorator',attributes={'mode':'one'}),dict(java_class='example.Decorator',attributes={'mode':'two'})]
    child2=format_node('CCString','second','example.String'); child2['attributes']['id']='first'
    reference=format_node('refFmt','reference');reference['reference_definition_id']='leaf'
    leaf=format_node('fmtDef','leaf');leaf['children']=[format_node('CCString','leaf-value','example.String')]
    body=format_node('CCIColl','body','example.Collection');body.update(collection_kind='indexed',children=[child1,child2,reference])
    definition=format_node('fmtDef','root');definition['children']=[body]
    unit=step('format-1');unit.update(kind='request_unformat',logical_id='Request',source_definition_id='root',
        effective_configuration=definition,referenced_definitions=[leaf],configuration_xml='<fmtDef id="Request"/>')
    item=operation([unit],[origin('example.String',['example.Helper']),origin('example.Helper'),origin('example.Collection'),origin('example.Decorator')])
    before=deepcopy(item)
    plan=build_component_plan({'INTERNET/A':item})
    assert plan.status=='planned' and item==before
    collection=next(node for node in plan.components.values() if node.kind=='format_node' and node.label=='CCIColl')
    assert collection.configuration['collection_kind']=='indexed'
    children=[plan.components[key] for key in collection.dependencies if plan.components[key].kind=='format_node']
    assert [node.provenance['selector'] for node in children]==['root/child:0/child:0','root/child:0/child:1','root/child:0/child:2']
    first=children[0]
    assert [record['attributes']['mode'] for record in first.configuration['decorators']]==['one','two']
    decorator=next(node for node in plan.components.values() if node.label=='example.Decorator')
    assert decorator.roles==['decorator'] and decorator.component_id in first.dependencies
    implementation=next(node for node in plan.components.values() if node.label=='example.String')
    assert {source['fqcn'] for source in implementation.provenance['supporting_sources']}=={'example.Helper'}
    assert children[2].dependencies and plan.components[children[2].dependencies[0]].label=='fmtDef'
    assert_order(plan)


def test_complex_call_is_a_contract_dependency_not_sibling_step_code():
    unit=step();unit['operation_calls']=[dict(callee='XML/Called',service_contract={'api_revision':'1'})]
    plan=build_component_plan({'SME/Caller':operation([unit],[origin('example.Work')])})
    contract=next(node for node in plan.components.values() if node.kind=='operation_contract')
    assert contract.label=='XML/Called' and contract.status=='external_recorded'
    assert contract.component_id in plan.components[plan.unit_roots['step-1']].dependencies


def test_cyclic_format_references_are_visible_but_not_reinterpreted_as_ready():
    first=format_node('fmtDef','first');second=format_node('fmtDef','second')
    to_second=format_node('refFmt','to-second');to_second['reference_definition_id']='second'
    to_first=format_node('refFmt','to-first');to_first['reference_definition_id']='first'
    first['children']=[to_second];second['children']=[to_first]
    unit=step('format');unit.update(kind='response_format',source_definition_id='first',effective_configuration=first,
                                  referenced_definitions=[second])
    plan=build_component_plan({'XML/Flow':operation([unit],[])})
    assert plan.status=='incomplete' and any('Cyclic configured format' in item['reason'] for item in plan.issues)
    assert any(group.cyclic and group.wave is None for group in plan.groups)
    assert_order(plan)


def test_cached_preparation_adds_plan_without_changing_units_routes_or_native_inputs(tmp_path,scoped_mapper,monkeypatch):
    from test_scoped_closure import import_workspace
    from test_scoped_workflow import settings,prepare
    from tools.conversion_tools.scoped_workflow import preparation
    from runtime.scoped_native.payloads import native_inputs
    conn,root,vault=import_workspace(tmp_path,scoped_mapper)
    config,profile=settings(root,vault)
    # Control the metadata hook only; original unit construction and source qualification run normally.
    with monkeypatch.context() as patch:
        empty=ComponentConversionPlan()
        empty.fingerprint=digest(empty.model_dump(mode='json',exclude={'fingerprint'}))
        patch.setattr(preparation,'build_component_plan',lambda *a,**k:empty)
        before=prepare(conn,config,profile)
    monkeypatch.setattr(preparation,'build_scoped_operation_closure',lambda *a,**k:pytest.fail('Cached closure must not rebuild'))
    after=prepare(conn,config,profile)
    assert after['operations']==before['operations'] and native_inputs(after)==native_inputs(before)
    plan=ComponentConversionPlan.model_validate(after['component_plan'])
    assert plan.status=='planned',plan.issues
    assert set(plan.unit_roots)=={unit['unit_id'] for item in before['operations'].values() for unit in item['units']}
    assert prepare(conn,config,profile)['component_plan']==after['component_plan']
    conn.close()


def test_fresh_bank_plan_retains_all_83_units_without_native_generation(tmp_path,scoped_mapper):
    from test_bank_boundary_harness import _prepare_bank
    report=_prepare_bank(tmp_path,scoped_mapper)
    plan=ComponentConversionPlan.model_validate(report['component_plan'])
    units=[unit for operation in report['operations'].values() for unit in operation.get('units',[])]
    assert len(units)==len(plan.unit_roots)==83
    assert plan.status=='planned',plan.issues[:10]
    assert all({'format_leaf','format_wrapper','step_implementation','decorator'}.intersection(node.roles)
               for node in plan.components.values() if node.kind=='java_implementation')
    supporting=[source for node in plan.components.values() if node.kind=='java_implementation'
                for source in node.provenance.get('supporting_sources',[])]
    assert any(node.label.endswith('.NilDecorator') and 'decorator' in node.roles for node in plan.components.values())
    assert any(source['fqcn'].endswith('.Context') for source in supporting)
    assert not plan.generation_enabled and not report['conversion_enabled']
    assert all(root in plan.components for root in plan.unit_roots.values())
    assert_order(plan)
    before=json.dumps(report['operations'],sort_keys=True)
    assert build_component_plan(report['operations']).model_dump(mode='json')==report['component_plan']
    assert json.dumps(report['operations'],sort_keys=True)==before
    import os
    export=os.environ.get('SNAPIR_COMPONENT_PLAN_EXPORT')
    if export: Path(export).write_text(plan.model_dump_json(indent=2),encoding='utf-8')


from test_scoped_vault_identity import scoped_mapper
