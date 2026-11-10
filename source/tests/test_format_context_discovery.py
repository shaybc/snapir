"""Evidence and fixture tests for nonexhaustive context discovery."""
import json
import pytest
from models.format_context_requirement import FormatContextDiscovery
from models.format_comparison_plan import FormatComparisonPlan
from models.format_comparison_settings import FormatComparisonSettings
from runtime.format_comparison.context_discovery import discover_context, validate_discovery
from runtime.format_comparison.cases import expand_fixtures, unresolved_inputs
from runtime.format_comparison.planning import original_unit


def channel_plan():
    code = 'if ("INTERNET".equals(ctx.getValueAt("runtime.channel"))) return "online";'
    import hashlib
    unit = original_unit([dict(identity='channel', content=code, content_hash=hashlib.sha256(code.encode()).hexdigest())],
                         dict(java_class='example.Format', attributes={}))
    citation = dict(source_identity='channel', excerpt=code)
    discovery = dict(requirements=[dict(requirement_id='channel', context_key='runtime.channel', value_type='string', citations=[citation],
        values=[dict(value='INTERNET', origin='source_backed', citations=[citation], branch_id='internet'),
                dict(value='SME', origin='exploratory')])])
    return FormatComparisonPlan(label='channels', scope='basic', original_unit=unit,
        native_sources=[dict(path='src/main/java/nativecode/Format.java', content='package nativecode; public class Format {}')],
        entries={'write': dict(direction='format', binding=dict(owner_type='nativecode.Format', method_name='format'))},
        cases=[dict(case_id='baseline', binding_id='write', initial_context={'runtime.channel': 'INTERNET'})], discovery=discovery)


def test_source_backed_and_exploratory_fixtures_keep_provenance(tmp_path):
    plan = channel_plan()
    plan.discovery.requirements[0].directions=['format']
    before = plan.model_dump_json()
    response = plan.discovery.model_dump_json()
    called = []
    def model(instruction, payload):
        called.append(json.loads(payload)); return response
    result = discover_context(plan.original_unit, model, FormatComparisonSettings(), tmp_path)
    assert result.requirements[0].context_key == 'runtime.channel'
    assert 'native_sources' not in called[0]
    assert called[0]['execution']['selected_directions']==['format']
    assert called[0]['execution']['entry_points']==[dict(direction='format',resolution='resolve_from_source',
        candidate_names=['format','beforeFormatDo','formatField'])]
    cases = expand_fixtures(plan, FormatComparisonSettings())
    assert len(cases) == 3
    assert cases[1].origin == 'source_backed' and cases[1].targeted_branch_ids == ['internet']
    assert cases[2].origin == 'exploratory' and cases[2].initial_context['runtime.channel'] == 'SME'
    assert plan.model_dump_json() == before


def test_invented_evidence_and_expected_results_are_rejected():
    plan = channel_plan(); plan.discovery.requirements[0].values[0].citations[0].excerpt = 'not in source'
    with pytest.raises(ValueError, match='citation'):
        validate_discovery(plan.discovery, plan.original_unit)
    with pytest.raises(ValueError):
        FormatContextDiscovery.model_validate(dict(requirements=[], expected_xml='<invented/>'))


def test_unknown_dynamic_input_is_unavailable_but_independent_case_can_run():
    plan = channel_plan()
    requirement = plan.discovery.requirements[0]
    requirement.context_key = None; requirement.unresolved_reason = 'Path depends on an unavailable helper'
    assert unresolved_inputs(plan, plan.cases[0])
    independent = plan.cases[0].model_copy(update={'required_inputs': []})
    assert not unresolved_inputs(plan, independent)


def test_case_budget_never_silently_drops_branches():
    with pytest.raises(ValueError, match='budget'):
        expand_fixtures(channel_plan(), FormatComparisonSettings(max_cases=1))


def test_discovery_failure_is_visible_not_empty_success(tmp_path):
    def fail(*args): raise TimeoutError()
    result = discover_context(channel_plan().original_unit, fail, FormatComparisonSettings(), tmp_path)
    assert result.unresolved and 'TimeoutError' in result.unresolved[0]


def test_unformat_discovery_receives_entry_direction_and_does_not_require_xml_outputs(tmp_path):
    plan=channel_plan();plan.original_unit['kind']='request_unformat'
    def model(instruction,encoded):
        payload=json.loads(encoded)
        assert payload['execution']==dict(unit_kind='request_unformat',selected_directions=['unformat'],
            entry_points=[dict(direction='unformat',resolution='resolve_from_source',
                candidate_names=['unformat','beforeUnformatDo','unformatField'])])
        assert 'XML fields' in instruction and 'context writes are not initial-context requirements' in instruction
        return FormatContextDiscovery().model_dump_json()
    discovery=discover_context(plan.original_unit,model,FormatComparisonSettings(),tmp_path)
    assert not discovery.requirements and not discovery.unresolved
    plan.discovery=discovery
    plan.entries['write'].direction='unformat'
    plan.cases=[plan.cases[0].model_copy(update=dict(case_id='xml-'+str(i),input_xml='<Value>'+str(i)+'</Value>',initial_context={})) for i in range(41)]
    assert len(expand_fixtures(plan,FormatComparisonSettings(max_cases=64)))==41


@pytest.mark.parametrize('directions',[None,[],['format'],['unformat','unformat']])
def test_new_unformat_discovery_rejects_missing_or_wrong_direction_labels(tmp_path,directions):
    discovery=channel_plan().discovery;discovery.requirements[0].directions=directions
    result=discover_context(channel_plan().original_unit,lambda *args:discovery.model_dump_json(),FormatComparisonSettings(),tmp_path,directions=['unformat'])
    assert result.unresolved


def test_direction_labels_keep_real_unformat_reads_and_do_not_expand_opposite_direction():
    plan=channel_plan();requirement=plan.discovery.requirements[0];requirement.directions=['format']
    plan.entries['read']=plan.entries['write'].model_copy(update={'direction':'unformat'})
    plan.cases.append(plan.cases[0].model_copy(update=dict(case_id='xml',binding_id='read',input_xml='<Value/>',initial_context={})))
    cases=expand_fixtures(plan,FormatComparisonSettings())
    assert len(cases)==4 and len([case for case in cases if case.binding_id=='read'])==1
    assert not unresolved_inputs(plan,plan.cases[1])
    requirement.directions=['unformat']
    assert unresolved_inputs(plan,plan.cases[1])
    assert len([case for case in expand_fixtures(plan,FormatComparisonSettings()) if case.binding_id=='read'])==3

