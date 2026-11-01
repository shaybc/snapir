"""Configured proof is source-backed; changed setters, Tag readers and runtime children stay open."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from models.pipeline_configuration import PipelineConfiguration
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from models.boundary_observation import BoundaryObservation
from models.executable_verification_settings import ExecutableVerificationSettings
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.configured_preparation import retain_preparation
from tools.behavior_verification.boundary_coverage import boundary_coverage
from tools.behavior_verification.input_scenarios import generate_input_scenarios
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first
from test_typed_boundary_adapter import ROOT


def original(*,left='true',setter=False,impure=False,mutate_children=False,reinitialize=False):
    tag='''package com.ibm.dse.base; import java.util.Map; import java.util.HashMap;
        public class Tag { private final Map<String,String> attributes=new HashMap<>();
        public Tag(Map<String,String> attributes){this.attributes.putAll(attributes);}
        public String getAttribute(String name){return attributes.get(name);} }'''
    if impure:tag=tag.replace('return attributes.get(name);','attributes.put(name,"false"); return attributes.get(name);')
    base='''package example; import com.ibm.dse.base.Context; import com.ibm.dse.base.Tag;
        import java.util.ArrayList; import java.util.List;
        public abstract class Base { private final List<Base> children=new ArrayList<>();
        public void initializeFrom(Tag tag){} public void addChild(Base child){children.add(child);}
        public abstract void unformat(String xml,Context context);
        protected void unformatChildren(String xml,Context context){for(Base child:children) child.unformat(xml,context);} }'''
    formatter='''package example; import com.ibm.dse.base.Context; import com.ibm.dse.base.Tag;
        public class Formatter extends Base { private boolean left=true;
        public void initializeFrom(Tag tag){String side=tag.getAttribute("left"); if(side != null && "false".equalsIgnoreCase(side)) this.left=false;}
        public void unformat(String xml,Context context){if(left) context.setValueAt("side","left"); else context.setValueAt("side","right"); unformatChildren(xml,context);}
        SETTER }'''.replace('SETTER','public void change(){left=false;}' if setter else '')
    if mutate_children:formatter=formatter.replace('if(left)', 'addChild(new Leaf()); if(left)')
    if reinitialize:formatter=formatter.replace('if(left)', 'initializeFrom(new Tag(java.util.Map.of("left","false"))); if(left)')
    leaf='''package example; import com.ibm.dse.base.Context; public class Leaf extends Base {
        public void unformat(String xml,Context context){context.setValueAt("value",xml);} }'''
    value=unit('request_unformat','example.Formatter',sources=[
        source('context',(ROOT/'com/ibm/dse/base/Context.java').read_text()),source('tag',tag),
        source('base',base),source('formatter',formatter),source('leaf',leaf)])
    value['effective_configuration']={'tag':'fmtDef','children':[dict(tag='Container',java_class='example.Formatter',
        attributes={'dataName':'Root','left':left},decorators=[],children=[dict(tag='String',java_class='example.Leaf',
            attributes={'dataName':'Value'},children=[],decorators=[])])]}
    return value


def analyze(tool,**options):
    value=original(**options)
    boundary=UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(value),tool_jar=tool)))
    assert boundary.legacy_method is not None,boundary.issues
    answers=UnitChecklistAnswers(unit_id=value['unit_id'],source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash)
    result,_=inspect_static_sources(value,boundary,{},answers,PipelineConfiguration().unit_verification_policy,tool)
    retain_preparation(boundary,result['preparation'])
    return value,boundary


@pytest.mark.parametrize('left,expected',[('true','true'),('false','false')])
def test_configured_fields_and_children_are_prepared_before_execution(boundary_tool,left,expected):
    value,boundary=analyze(boundary_tool,left=left)
    plan=boundary.configuration_preparation
    branch=next(i for i in boundary.parser_checklist.items if i.kind=='branch' and i.properties.get('condition')=='left')
    assert plan['branches'][branch.id]['allowed_outcomes']==[expected]
    short=next(i for i in boundary.parser_checklist.items if i.kind=='branch' and i.detail=='short_circuit')
    assert plan['branches'][short.id]['allowed_outcomes']==['true']
    assert len(plan['dispatches'])==1,plan
    proof=next(iter(plan['dispatches'].values()))
    assert proof['configured_child_types']==['example.Leaf']
    assert all(next(n for n in boundary.reachable_slice.nodes if n.id==key).declaring_class=='example.Leaf' for key in proof['candidates'])
    raw=boundary_coverage(boundary,[])
    item=next(b for b in raw['branches'] if b['checklist_id']==branch.id)
    assert item['unexercised_outcomes']==[expected] and item['observed_outcomes']==[]
    opposite='false' if expected=='true' else 'true'
    conflict=boundary_coverage(boundary,[BoundaryObservation(case_id='conflict',status='completed',probes=[dict(id=branch.id,outcome=opposite)])])
    assert branch.id in conflict['configuration_proof_conflicts']
    before=deepcopy(value['effective_configuration'])
    cases,_=generate_input_scenarios(value,boundary,ExecutableVerificationSettings(mode='executable_boundary_v1'))
    assert any('configured-preparation:leading-xml-whitespace' in c.labels for c in cases)
    assert value['effective_configuration']==before


@pytest.mark.parametrize('options',[{'setter':True},{'impure':True},{'reinitialize':True}])
def test_unproved_or_mutable_configuration_is_not_excluded(boundary_tool,options):
    _,boundary=analyze(boundary_tool,**options)
    branch=next(i for i in boundary.parser_checklist.items if i.kind=='branch' and i.properties.get('condition')=='left')
    assert branch.id not in boundary.configuration_preparation['branches']


def test_runtime_child_addition_keeps_dispatch_unresolved(boundary_tool):
    _,boundary=analyze(boundary_tool,mutate_children=True)
    assert not boundary.configuration_preparation['dispatches']
    assert boundary_coverage(boundary,[])['unresolved_edges']


def test_changed_source_proof_is_rejected(boundary_tool):
    _,boundary=analyze(boundary_tool)
    plan=deepcopy(boundary.configuration_preparation)
    next(iter(plan['branches'].values()))['source_hash']='wrong'
    with pytest.raises(ValueError,match='source changed'):retain_preparation(boundary,plan)
    plan=deepcopy(boundary.configuration_preparation)
    boundary.configuration_hash='different XML'
    with pytest.raises(ValueError,match='revision changed'):retain_preparation(boundary,plan)


def test_receipt_cannot_accept_contradicted_proof_even_when_both_outcomes_were_observed(boundary_tool):
    from runtime.behavior_conversion.coverage_receipts import coverage_inventory,require_coverage_evidence
    _,boundary=analyze(boundary_tool)
    identity=next(iter(boundary.configuration_preparation['branches']))
    observations=[BoundaryObservation(case_id=value,status='completed',probes=[dict(id=identity,outcome=value)]) for value in ['true','false']]
    report=SimpleNamespace(coverage=boundary_coverage(boundary,observations),cases=[dict(legacy=o.model_dump(mode='json')) for o in observations])
    structure=dict(coverage_inventory=coverage_inventory(boundary),source_manifest_hash=boundary.source_manifest_hash,configuration_hash=boundary.configuration_hash)
    with pytest.raises(ValueError,match='contradict configured preparation'):
        require_coverage_evidence(structure,{},report,ExecutableVerificationSettings(mode='executable_boundary_v1'))
