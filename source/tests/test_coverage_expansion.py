"""Coverage exploration is deterministic, measured, bounded and never a production repair."""
from types import SimpleNamespace
from copy import deepcopy
import time
import pytest
from models.boundary_case import BoundaryCase
from models.boundary_observation import BoundaryObservation
from models.boundary_comparison_report import BoundaryComparisonReport
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.executable_verification_settings import ExecutableVerificationSettings
from tools.behavior_verification.coverage_expansion import CoverageExpansion,VERSION
from tools.behavior_verification.coverage_inputs import proposals
from tools.behavior_verification.boundary_coverage import boundary_coverage
from runtime.behavior_conversion.coverage_receipts import coverage_inventory,require_coverage_evidence


def setup(**limits):
    fields=dict(code_node_id='method',source_identity='work')
    branch=SimpleNamespace(**fields,id='branch',kind='branch',detail='if',source_file='Work.java',start_line=1,
        properties={'condition':'"OPEN".equals(context.getValueAt("flag"))'})
    key=SimpleNamespace(**fields,id='key',kind='literal',detail='StringLiteralExpr',excerpt='"flag"',properties={'value':'flag'})
    value=SimpleNamespace(**fields,id='value',kind='literal',detail='StringLiteralExpr',excerpt='"OPEN"',properties={'value':'OPEN'})
    call=SimpleNamespace(**fields,id='call',kind='call',detail='method',excerpt='context.getValueAt("flag")',
        arguments=['"flag"'],properties={'target':'com.ibm.dse.base.Context.getValueAt(java.lang.String)'})
    boundary=SimpleNamespace(parser_checklist=SimpleNamespace(items=[branch,key,value,call]),
        reachable_slice=SimpleNamespace(nodes=[SimpleNamespace(id='method',kind='method')],edges=[]))
    policy=ExecutableVerificationSettings(mode='executable_boundary_v1',**limits)
    unit=dict(unit_id='u',kind='configured_step',effective_configuration={'attributes':{}},referenced_definitions=[])
    binding=BoundaryHarnessBinding(adapter_class='legacy.Adapter')
    return unit,boundary,policy,binding


def report_for(boundary,cases,outcome='false'):
    observations=[BoundaryObservation(case_id=case.case_id,status='completed',exception=None,
        probes=[{'id':'method','outcome':'entered'},{'id':'branch','outcome':outcome}]) for case in cases]
    return BoundaryComparisonReport(unit_id='u',source_manifest_hash='s',configuration_hash='c',coverage=boundary_coverage(boundary,observations),
        cases=[dict(case=case.model_dump(mode='json'),legacy=observation.model_dump(mode='json'),comparison_status='matched') for case,observation in zip(cases,observations)])


def test_recognized_inputs_preserve_controls_and_stop_without_progress():
    unit,boundary,policy,binding=setup();base=BoundaryCase(case_id='base',initial_context={'flag':'123'},clock_millis=73,
        settings=[{'class':'Setting','method':'configure','arguments':[[]]}],external_responses=[{'target':'lookup','arguments':[],'value':'fixed'}])
    report=report_for(boundary,[base]);expansion=CoverageExpansion(unit,boundary,policy,binding)
    added=expansion.propose(report)
    assert added and any(case.initial_context.get('flag')=='OPEN' for case in added)
    assert all(case.clock_millis==73 and case.settings==base.settings and case.external_responses==base.external_responses for case in added)
    expanded=report_for(boundary,[base,*added])
    assert expansion.propose(expanded)==[] and expansion.reason=='no_progress'
    assert len(expansion.rounds)==1 and len(expansion.ids)<=policy.coverage_expansion_cases


@pytest.mark.parametrize('setting,expected',[({'coverage_expansion_cases':1},'case_budget'),({'coverage_expansion_rounds':0},'disabled')])
def test_policy_limits_terminate_exploration(setting,expected):
    unit,boundary,policy,binding=setup(**setting);base=BoundaryCase(case_id='base',initial_context={'flag':'123'})
    report=report_for(boundary,[base]);expansion=CoverageExpansion(unit,boundary,policy,binding)
    if expected=='case_budget':expansion.ids.add('already-planned')
    expansion.propose(report)
    assert expansion.reason==expected


def test_unsupported_conditions_and_deadline_are_explicit():
    unit,boundary,policy,binding=setup();base=BoundaryCase(case_id='base',initial_context={'flag':'123'})
    report=report_for(boundary,[base]);boundary.parser_checklist.items[0].properties['condition']='unknownHelper()'
    expansion=CoverageExpansion(unit,boundary,policy,binding)
    assert expansion.propose(report)==[] and expansion.unsupported['branch']=='condition_has_no_unique_supported_input'
    unit,boundary,policy,binding=setup();clock=[0.0]
    expansion=CoverageExpansion(unit,boundary,policy,binding,clock=lambda:clock[0]);expansion.propose(report_for(boundary,[base]))
    clock[0]=31
    assert expansion.propose(report_for(boundary,[base]))==[] and expansion.reason=='time_budget'


def test_xml_proposals_preserve_paths_prefixes_and_reject_ambiguity():
    unit,boundary,_,binding=setup();unit['kind']='request_unformat'
    leaf=lambda name:dict(attributes={'dataName':name},children=[])
    unit['effective_configuration']=dict(attributes={'dataName':'Root'},children=[dict(attributes={'dataName':'Left'},children=[leaf('flag')])])
    baseline=BoundaryCase(case_id='xml',input_xml='<Root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><Left><flag>old</flag></Left></Root>')
    candidates,reason=proposals(unit,boundary,boundary.parser_checklist.items[0],baseline,binding)
    assert reason is None
    xml=[case.input_xml for case in candidates]
    assert any('<Left><flag>OPEN</flag></Left>' in value for value in xml)
    assert all('ns0:' not in value for value in xml)
    baseline.input_xml='<Root xmlns:xsi="urn:business"><Left><flag>old</flag></Left><xsi:Other/></Root>'
    candidates,_=proposals(unit,boundary,boundary.parser_checklist.items[0],baseline,binding)
    nil=next(case.input_xml for case in candidates if ':nil="true"' in case.input_xml)
    assert 'xmlns:xsi="urn:business"' in nil and 'xsi1:nil="true"' in nil and '<xsi:Other/>' in nil
    unit['effective_configuration']['children'].append(dict(attributes={'dataName':'Right'},children=[leaf('flag')]))
    candidates,_=proposals(unit,boundary,boundary.parser_checklist.items[0],baseline,binding)
    assert not list(candidates)


def test_expired_deadline_prevents_launching_a_jvm(monkeypatch,tmp_path):
    from tools.behavior_verification.boundary_execution import execute_boundary_case
    from test_behavior_verification_boundaries import unit
    original=unit();boundary=SimpleNamespace(implementation_class='example.Work')
    def forbidden(*args,**kwargs):raise AssertionError('Expired work must not launch Java')
    monkeypatch.setattr('tools.behavior_verification.boundary_execution._run',forbidden)
    observation=execute_boundary_case(dict(directory=tmp_path,classpath=['unused']),original,boundary,
        BoundaryHarnessBinding(adapter_class='fixture.Adapter'),BoundaryCase(case_id='expired'),deadline=time.monotonic()-1)
    assert observation.status=='verification_incomplete'


def test_coverage_receipt_recomputes_branch_outcomes():
    unit,boundary,policy,binding=setup(coverage_expansion_rounds=0)
    report=report_for(boundary,[BoundaryCase(case_id='base')]);expansion=CoverageExpansion(unit,boundary,policy,binding)
    expansion.propose(report);record=expansion.record(report)
    report.execution_environment['coverage_expansion']=record
    structure=dict(coverage_expansion_version=VERSION,coverage_inventory=coverage_inventory(boundary))
    receipt={'coverage_expansion':deepcopy(record)}
    require_coverage_evidence(structure,receipt,report,policy)
    report=BoundaryComparisonReport.model_validate_json(report.model_dump_json())
    require_coverage_evidence(structure,receipt,report,policy)
    report.execution_environment['coverage_expansion']['additional_cases']=1
    receipt['coverage_expansion']['additional_cases']=1
    with pytest.raises(ValueError,match='policy or does not match'):require_coverage_evidence(structure,receipt,report,policy)
    report.execution_environment['coverage_expansion']['additional_cases']=0
    receipt['coverage_expansion']['additional_cases']=0
    report.coverage['branches'][0]['unexercised_outcomes']=[]
    with pytest.raises(ValueError,match='original probes'):require_coverage_evidence(structure,receipt,report,policy)
