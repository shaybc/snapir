"""Deterministic controls preserve structure and remain independent of expected outputs."""
from types import SimpleNamespace
from copy import deepcopy
from xml.etree import ElementTree as ET
import pytest
from models.executable_verification_settings import ExecutableVerificationSettings
from runtime.behavior_conversion.verification_cases import controlled_cases
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.behavior_verification.input_scenarios import generate_input_scenarios
from tools.behavior_verification.structured_inputs import generate_xml_cases
from tools.behavior_verification.input_domains import scalar_domain


def leaf(name,**attributes):return {'attributes':dict(dataName=name,**attributes),'children':[]}
def container(name,*children):return {'attributes':{'dataName':name},'children':list(children)}
def boundary(*literals):
    return SimpleNamespace(parser_checklist=SimpleNamespace(items=[SimpleNamespace(kind='literal',detail='IntegerLiteralExpr',
        excerpt=str(n),properties={'value':str(n)}) for n in literals]))
def unit(tree,kind='request_unformat'):
    return dict(unit_id='u',kind=kind,effective_configuration=tree,referenced_definitions=[])
def policy(**overrides):return ExecutableVerificationSettings(mode='executable_boundary_v1',random_cases=0,**overrides)


def test_nested_duplicate_names_are_not_flattened_and_inputs_repeat_exactly():
    original=unit(container('Root',container('Left',leaf('Id')),container('Right',leaf('Id'))))
    cases,report=generate_xml_cases(original,boundary(42),policy())
    assert (cases,report)==generate_xml_cases(original,boundary(42),policy())
    base=ET.fromstring(cases[0].input_xml)
    assert base.findtext('Left/Id')=='123' and base.findtext('Right/Id')=='123' and base.find('Id') is None
    assert any('/Root/Left/Id'==p['xml_path'] for p in report['paths'])
    assert any('/Root/Right/Id'==p['xml_path'] for p in report['paths'])
    values=[]
    for case in cases:
        if not case.input_xml:continue
        root=ET.fromstring(case.input_xml);left=root.find('Left/Id');right=root.find('Right/Id')
        if left is not None and right is not None and right.text=='123':values.append(left.text)
    assert {'41','42','43'}<=set(values)


def test_missing_nil_empty_and_escaped_text_are_separate_inputs():
    cases,_=generate_xml_cases(unit(container('Root',leaf('Value'))),boundary(),policy())
    roots=[ET.fromstring(c.input_xml) for c in cases if c.input_xml]
    assert any(r.find('Value') is None and not r.attrib for r in roots)
    assert any(r.find('Value') is not None and r.find('Value').get('{http://www.w3.org/2001/XMLSchema-instance}nil')=='true' for r in roots)
    assert any(r.find('Value') is not None and not r.find('Value').attrib and r.find('Value').text is None for r in roots)
    assert any(r.findtext('Value')=='a&<b>' for r in roots)


def test_references_and_explicit_repeated_elements_keep_their_structure():
    reference={'reference_definition_id':'fields','attributes':{},'children':[]}
    value=unit(container('Root',reference))
    value['referenced_definitions']=[dict(definition_id='fields',attributes={},children=[leaf('Item',minOccurs='2',maxOccurs='2')])]
    cases,report=generate_xml_cases(value,boundary(),policy())
    counts={len(ET.fromstring(c.input_xml).findall('Item')) for c in cases if c.input_xml}
    assert {0,1,2}<=counts and report['collection_paths']==1
    assert len(ET.fromstring(cases[0].input_xml).findall('Item'))==2
    value['referenced_definitions'][0]['children']=[reference]
    with pytest.raises(ValueError,match='cyclic'):generate_xml_cases(value,boundary(),policy())


def test_patterns_and_literal_sampling_are_bounded():
    baseline,values,omitted=scalar_domain({'pattern':'yyyyMMdd'},boundary(*range(20)).parser_checklist,limit=12)
    assert baseline=='20240102' and len(values)==12 and omitted>0
    assert policy().max_domain_values>=11
    date_cases,_=generate_input_scenarios(unit(container('Root',leaf('Date',pattern='yyyyMMdd')),kind='response_format'),boundary(),policy())
    assert all(c.initial_context.get('Date') is None or isinstance(c.initial_context['Date'],dict) for c in date_cases)
    base,decimal_values,_=scalar_domain({'type':'decimal','maxInclusive':'9.5'},boundary('9.5').parser_checklist)
    assert base=='9.5' and {'8.5','9.5','10.5'}<=set(decimal_values)


def test_unit_scoped_fixtures_and_replays_do_not_invent_expected_outputs():
    settings=policy(fixtures={'u':[dict(case_id='captured',input_xml='<Root/>',external_responses=[
        {'target':'lookup','arguments':['id'],'value':None}])]},replays={'u':[{'target':'lookup','arguments':['id'],'value':'supplied'}]})
    cases,report=generate_input_scenarios(unit(container('Root',leaf('Id'))),boundary(),settings)
    assert report['fixture_cases']==1 and cases[-1].external_responses[0]['value'] is None
    assert cases[0].external_responses[0]['value']=='supplied'
    cases[0].external_responses[0]['value']='changed'
    assert settings.replays['u'][0]['value']=='supplied'
    other=unit(container('Root',leaf('Id')));other['unit_id']='other'
    assert not generate_input_scenarios(other,boundary(),settings)[0][0].external_responses
    with pytest.raises(ValueError):policy(fixtures={'u':[dict(case_id='bad',expected_output='invented')]})
    with pytest.raises(ValueError):policy(replays={'u':[{'target':'lookup','arguments':[],'expected':'invented'}]})


def test_budget_and_unknown_shapes_stay_incomplete():
    value=unit(container('Root',leaf('Value')))
    with pytest.raises(VerificationIncomplete,match='budget'):
        controlled_cases(value,boundary(),SimpleNamespace(settings_bindings={}),[],executable_settings=policy(max_cases=2))
    value['effective_configuration']['collection_kind']='indexed'
    with pytest.raises(ValueError,match='occurrence layout'):generate_xml_cases(value,boundary(),policy())
    with pytest.raises(ValueError,match='size budget'):
        generate_input_scenarios(unit(container('Root',leaf('Value'))),boundary(),policy(max_case_chars=256,
            replays={'u':[{'target':'service','arguments':[],'value':'x'*300}]}))


def test_settings_cartesian_product_is_stopped_at_the_case_limit():
    value=unit({'attributes':{},'children':[]},kind='configured_step')
    binding=SimpleNamespace(settings_bindings={'original.Settings.configure':{'class':'native.Settings','method':'configure'}})
    with pytest.raises(VerificationIncomplete,match='product exceeds'):
        controlled_cases(value,boundary(),binding,[{'target':'original.Settings.configure','arity':20}],executable_settings=policy(max_cases=8))


def test_context_boundaries_include_literals_and_keep_missing_distinct_from_null():
    value=unit(container('Root',leaf('Amount')),kind='response_format')
    cases,report=generate_input_scenarios(value,boundary(42),policy())
    assert {'41','42','43'}<={c.initial_context.get('Amount') for c in cases}
    assert any('Amount' not in c.initial_context for c in cases)
    assert any('Amount' in c.initial_context and c.initial_context['Amount'] is None for c in cases)
    assert report['sampled_paths']==1


def test_fixture_contents_are_not_delivered_to_the_model_and_invalidate_reuse():
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.behavior_conversion.verification_mode import policy_payload
    from tools.conversion_tools.scoped_reuse.fingerprints import conversion_policy
    profile=PipelineConfiguration(executable_verification=policy(replays={'u':[{'target':'private-fixture','arguments':[],'value':'held-out-value'}]}))
    encoded=str(policy_payload(profile))
    assert 'held-out-value' not in encoded and 'private-fixture' not in encoded
    changed=profile.model_copy(deep=True);changed.executable_verification.replays['u'][0]['value']='other'
    assert conversion_policy(profile)!=conversion_policy(changed)
