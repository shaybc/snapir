"""Milestone 5 mapping/exclusion safeguards, independent of live conversion acceptance."""
from copy import deepcopy
import hashlib
import pytest
from pydantic import ValidationError
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from models.static_check_policy import StaticCheckPolicy
from models.checklist_response import ChecklistResponse
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_checks import validate_unit_static
from tools.behavior_verification.checklist_mapping import candidate_digest
from tools.behavior_verification.boundary_contracts import digest
from test_behavior_verification_boundaries import boundary_tool, source, unit, prepared, first


NATIVE = [dict(path='src/main/java/nativecode/Work.java', content='''package nativecode;
public class Work {
    // comment-only-evidence
    public int execute() { return 0; }
    private String helper() { return "unused"; }
}''')]


def analyze(boundary_tool, text=None):
    original = unit(sources=[source('work', text or '''package example;
public class Work {
    public int execute() {
        if (false) { return 99; }
        return 7;
    }
}''')])
    boundary = UnitVerificationBoundary.model_validate(first(build_boundary_report(prepared(original), tool_jar=boundary_tool)))
    assert boundary.parser_checklist.status == 'extracted', boundary.parser_checklist.issues
    answers = UnitChecklistAnswers(unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash, responses=[ChecklistResponse(checklist_id=item.id, status='implemented',
            locations=[dict(path=NATIVE[0]['path'], excerpt='return 0;')]) for item in boundary.parser_checklist.items])
    return original, boundary, answers


def answer_for(answers, identity, **values):
    answers.responses = [ChecklistResponse(checklist_id=answer.checklist_id, **values) if answer.checklist_id == identity else answer
                         for answer in answers.responses]


def check(data, boundary_tool, **kwargs):
    original, boundary, answers = data
    return validate_unit_static(original, boundary, kwargs.pop('files', NATIVE), answers, tool=boundary_tool, **kwargs)


def test_valid_mapping_is_not_acceptance_and_missing_literal_is_warning(boundary_tool, tmp_path):
    data = analyze(boundary_tool)
    report = check(data, boundary_tool, directory=tmp_path)
    assert report.status == 'mapping_valid', report.errors
    assert report.warnings and report.comparison_requests
    assert any(request['case_ids'] for request in report.comparison_requests)
    assert report.comparison_cases
    assert all(not item['equivalence_proven'] for item in report.literal_checks)
    assert not report.acceptance_gate_enabled and report.behavioral_verification == 'not_decided'
    assert (tmp_path / 'unit-static-checks.json').exists()


def test_missing_answer_does_not_hide_other_independent_bad_citations(boundary_tool):
    data=analyze(boundary_tool)
    assert len(data[2].responses)>2
    missing=data[2].responses.pop().checklist_id
    bad=data[2].responses[0].checklist_id
    data[2].responses[0].locations[0].excerpt='comment-only-evidence'
    report=check(data,boundary_tool)
    assert report.status=='mapping_invalid'
    assert {missing,bad}.issubset({e.get('checklist_id') for e in report.errors})


def test_batched_whole_unit_retains_existing_ast_policy_and_assembles_answers(boundary_tool,monkeypatch):
    import json
    from types import SimpleNamespace
    from models.native_implementation import NativeImplementation
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.behavior_conversion.metadata_checklist import map_checklist
    from runtime.behavior_conversion.native_metadata import inspect_native
    from tests.runtime.test_behavior_conversion import state
    original,boundary,_=analyze(boundary_tool)
    session=SimpleNamespace(unit=original,boundary=boundary,policy=StaticCheckPolicy(),authorizations=[],tool=boundary_tool)
    monkeypatch.setattr('runtime.behavior_conversion.verification_ladder.active_verification',lambda:session)
    conn,config=state();seen=[]
    def model(prompt,text):
        req=json.loads(text);seen.append(req)
        return json.dumps(dict(task_revision=req['task_revision'],production_revision=req['production_revision'],batch_id=req['batch_id'],
            entries=[dict(checklist_id=i['id'],status='implemented',locations=[dict(path=NATIVE[0]['path'],excerpt='return 0;')]) for i in req['assigned_items']]))
    profile=PipelineConfiguration(metadata_checklist_batch_items=2)
    tasks=SimpleNamespace(conn=conn,config=config,profile=profile,identity='unit-fixture',revision='r',model_call=model,
        validator=SimpleNamespace(stage_prerequisites={}),fresh=lambda:None)
    production=NativeImplementation(files=NATIVE)
    inventory=inspect_native(production.files,boundary_tool,original['sources'])
    try:
        mapped=map_checklist(tasks,{},production,inventory)
        assert len(mapped['checklist_answers']['responses'])==len(boundary.parser_checklist.items)
        report=validate_unit_static(original,boundary,NATIVE,mapped['checklist_answers'],tool=boundary_tool)
        assert report.status=='mapping_valid' and not report.acceptance_gate_enabled
        assert all(len(r['assigned_items'])<=2 and r['context']['boundary']['unit_id']==boundary.unit_id for r in seen)
    finally:conn.close()


def test_full_format_semantics_joins_required_answers_after_mapping(boundary_tool,monkeypatch):
    import json
    from types import SimpleNamespace
    from models.native_format_component_bundle import NativeFormatComponentBundle
    from models.native_implementation import NativeImplementation
    from models.native_test_bundle import NativeTestBundle
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.behavior_conversion.generation import generate
    from tests.runtime.test_behavior_conversion import state
    from test_staged_pipeline import request,Validator,TEST_PATH,TEST
    original,boundary,_=analyze(boundary_tool)
    session=SimpleNamespace(unit=original,boundary=boundary,policy=None,authorizations=(),tool=boundary_tool)
    monkeypatch.setattr('runtime.behavior_conversion.verification_ladder.active_verification',lambda:session)
    monkeypatch.setattr('runtime.component_conversion.scope.require_component_task',lambda *a:None)
    payload=request('format_composition');payload['configured_format']={'unit_id':boundary.unit_id}
    payload['sources']=original['sources'];payload['parser_checklist']=[i.model_dump(mode='json') for i in boundary.parser_checklist.items]
    native=[dict(path='src/main/java/com/company/generated/Work.java',content=NATIVE[0]['content'].replace('package nativecode;','package com.company.generated;'))]
    conn,config=state();validator=Validator();calls=[]
    def model(prompt,text):
        req=json.loads(text);title=req['schema']['title'];calls.append(title)
        if title=='NativeImplementation':return NativeImplementation(files=native).model_dump_json()
        if title=='NativeFormatComponentSemantics':
            assert 'checklist_answers' not in req['schema']['properties']
            return json.dumps(dict(contracts={'component':dict(api_types=['com.company.generated.Work'])},
                verification_binding=dict(owner_type='com.company.generated.Work',method_name='execute')))
        if title=='MetadataChecklistBatch':
            return json.dumps(dict(task_revision=req['task_revision'],production_revision=req['production_revision'],batch_id=req['batch_id'],
                entries=[dict(checklist_id=i['id'],status='implemented',locations=[dict(path=native[0]['path'],excerpt='return 0;')]) for i in req['assigned_items']]))
        assert title=='NativeTestBundle'
        return NativeTestBundle(files=[dict(path=TEST_PATH,content=TEST)],coverage={k:[TEST_PATH] for k in req['requirements']}).model_dump_json()
    try:
        bundle,_=generate(conn,config,PipelineConfiguration(model_provider='mock',java_version=25),
            'component_generation','format-fixture','unused',payload,NativeFormatComponentBundle,validator=validator,model_call=model)
        assert bundle.checklist_answers.unit_id==boundary.unit_id
        assert len(bundle.checklist_answers.responses)==len(boundary.parser_checklist.items)
        assert calls==['NativeImplementation','NativeFormatComponentSemantics','MetadataChecklistBatch','NativeTestBundle']
        assert validator.checks==1
    finally:conn.close()


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'unknown', 'stale'])
def test_exact_checklist_coverage_and_revision(boundary_tool, change):
    data = analyze(boundary_tool)
    answers = data[2]
    if change == 'missing': answers.responses.pop()
    if change == 'duplicate': answers.responses.append(answers.responses[0])
    if change == 'unknown': answers.responses[0].checklist_id = 'check-invented'
    if change == 'stale': answers.configuration_hash = 'old'
    report = check(data, boundary_tool)
    assert report.status == 'mapping_invalid' and report.errors


@pytest.mark.parametrize('excerpt', ['comment-only-evidence', 'package nativecode;', 'not in code'])
def test_comments_package_and_missing_citations_rejected(boundary_tool, excerpt):
    data = analyze(boundary_tool)
    data[2].responses[0].locations[0].excerpt = excerpt
    report = check(data, boundary_tool)
    assert report.status == 'mapping_invalid'
    assert data[2].responses[0].checklist_id in {error.get('checklist_id') for error in report.errors}


def test_helper_excerpt_can_cover_many_items_but_test_file_cannot(boundary_tool):
    data = analyze(boundary_tool)
    for answer in data[2].responses: answer.locations[0].excerpt = 'return "unused";'
    assert check(data, boundary_tool).status == 'mapping_valid'
    files = NATIVE + [dict(path='src/test/java/nativecode/WorkTest.java', content='package nativecode; class WorkTest { int test() { return 0; } }')]
    data[2].responses[0].locations[0].path = files[1]['path']
    data[2].responses[0].locations[0].excerpt = 'return 0;'
    assert check(data, boundary_tool, files=files).status == 'mapping_invalid'


def test_constant_dead_branch_is_proven_but_live_path_is_not(boundary_tool):
    data = analyze(boundary_tool)
    dead = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == '99')
    answer_for(data[2], dead.id, status='not_applicable', reason='branch_fixed_off')
    report = check(data, boundary_tool)
    assert report.status == 'mapping_valid', report.errors
    assert next(value for value in report.decisions if value['checklist_id'] == dead.id)['proof']['predicate'] == 'false'
    live = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == '7')
    answer_for(data[2], live.id, status='not_applicable', reason='branch_fixed_off')
    assert check(data, boundary_tool).status == 'mapping_invalid'


@pytest.mark.parametrize('reason', ['other_direction', 'uncertain_target_not_selected', 'framework_plumbing'])
def test_unproven_exclusions_do_not_drop_behavior(boundary_tool, reason):
    data = analyze(boundary_tool)
    literal = next(item for item in data[1].parser_checklist.items if item.kind == 'literal' and item.properties.get('value') == '7')
    answer_for(data[2], literal.id, status='not_applicable', reason=reason, rule_id='configured_setup_marker' if reason == 'framework_plumbing' else None)
    assert check(data, boundary_tool).status == 'mapping_invalid'


def test_dynamic_branch_and_mutable_local_do_not_become_configuration_proofs(boundary_tool):
    data = analyze(boundary_tool, '''package example; public class Work {
        boolean flag; public int execute() { boolean local = false; local = flag; if(local) return 99; return 7; }
    }''')
    item = next(item for item in data[1].parser_checklist.items if item.properties.get('value') == '99')
    answer_for(data[2], item.id, status='not_applicable', reason='branch_fixed_off')
    assert check(data, boundary_tool).status == 'mapping_invalid'


def test_explicit_approval_is_separate_and_exact_revision_bound(boundary_tool):
    data = analyze(boundary_tool)
    identity = data[2].responses[0].checklist_id
    answer_for(data[2], identity, status='not_applicable', reason='approved_exception', approval_id='fixture-approval')
    boundary = data[1]
    approval = dict(approval_id='fixture-approval', approved_by='test-fixture-only', approved_at='2026-10-27T00:00:00Z',
        unit_id=boundary.unit_id, source_manifest_hash=boundary.source_manifest_hash, configuration_hash=boundary.configuration_hash,
        candidate_hash=candidate_digest({file['path']: file['content'] for file in NATIVE}), checklist_id=identity,
        rationale='Synthetic test approval, never a production exception')
    assert check(data, boundary_tool).status == 'mapping_invalid'
    report = check(data, boundary_tool, authorizations=[approval])
    assert report.status == 'mapping_valid' and report.authorization_receipts
    changed = deepcopy(NATIVE); changed[0]['content'] += '\n'
    assert check(data, boundary_tool, authorizations=[approval], files=changed).status == 'mapping_invalid'
    with pytest.raises(ValidationError):
        ChecklistResponse(checklist_id=identity, status='not_applicable', reason='other_direction', human_approved=True)


def test_unresolved_stays_incomplete_and_unsafe_paths_rejected(boundary_tool):
    data = analyze(boundary_tool)
    answer_for(data[2], data[2].responses[0].checklist_id, status='unresolved', question='Which external contract applies?')
    assert check(data, boundary_tool).status == 'verification_incomplete'
    assert check(data, boundary_tool, files=[dict(path='../Work.java', content='class Work {}')]).status == 'mapping_invalid'


def test_unused_literal_presence_does_not_establish_equivalence(boundary_tool):
    data = analyze(boundary_tool)
    files = deepcopy(NATIVE); files[0]['content'] = files[0]['content'].replace('"unused"', '"xsi:" + "nil"')
    # Use the native inventory through a real original literal, including concatenated construction.
    data = analyze(boundary_tool, 'package example; public class Work { public int execute() { String name="xsi:nil"; return 7; } }')
    report = check(data, boundary_tool, files=files)
    literal = next(value for value in report.literal_checks if value['value'] == 'xsi:nil')
    assert literal['status'] == 'present_in_code' and not literal['equivalence_proven']
    assert report.behavioral_verification == 'not_decided'


def test_report_preserves_isolated_utf16_literal(boundary_tool, tmp_path):
    import json
    data = analyze(boundary_tool, r'package example; public class Work { public int execute() { String text="\uD800"; return 0; } }')
    report = check(data, boundary_tool, directory=tmp_path)
    assert report.status == 'mapping_valid', report.errors
    saved = json.loads((tmp_path / 'unit-static-checks.json').read_text(encoding='utf-8'))
    assert any(item['value'] == chr(0xd800) for item in saved['literal_checks'])
