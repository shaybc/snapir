"""Check material comparison findings and feedback without rejecting implementation style."""

import json

import pytest

from models.behavior_specification import BehaviorSpecification
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.behavior_fact_validation import validate_specification, validate_implementations
from runtime.behavior_conversion.review import review_behavior
from tests.runtime.test_behavior_conversion import state, profile
from tests.runtime.test_behavior_extraction import source, fact


def evidence():
    original = source()
    specification = BehaviorSpecification(facts=[fact(original)])
    validate_specification(specification, [original])
    path = 'src/main/java/com/company/generated/Mapper.java'
    content = 'package com.company.generated; public class Mapper { void write() { emit("xsi:nil", "true"); } }'
    payload = dict(sources=[original], behavior_specification=specification.model_dump(mode='json'),
                   generated_bundle=dict(files=[dict(path=path, content=content)]))
    finding = dict(fact_id=specification.facts[0].fact_id, status='matched', rationale='Source condition and output preserved',
        source_evidence=[dict(identity=original['identity'], content_hash=original['content_hash'], excerpt=original['content'])],
        generated_evidence=[dict(path=path, excerpt='emit("xsi:nil", "true")')])
    return payload, finding


@pytest.mark.parametrize('status', ['matched', 'missing', 'changed', 'invented_behavior', 'insufficient_evidence'])
def test_findings_produce_explicit_acceptance_corrections_or_evidence_questions(status):
    conn, config = state()
    payload, finding = evidence()
    finding.update(status=status, trigger='enabled and empty input', consequence='Observable attribute differs')
    result, _ = review_behavior(conn, config, profile(), 'unit', payload,
        lambda *_: json.dumps(dict(findings=[finding])))
    assert result.approved == (status == 'matched')
    assert bool(result.issues) == (status in {'missing', 'changed', 'invented_behavior'})
    assert bool(result.unresolved_questions) == (status == 'insufficient_evidence')


def test_style_advice_does_not_trigger_regeneration():
    conn, config = state()
    payload, finding = evidence()
    advice = dict(fact_id=None, status='non_behavioral_difference', rationale='Helper has a different name')
    result, _ = review_behavior(conn, config, profile(), 'unit', payload,
        lambda *_: json.dumps(dict(findings=[finding, advice])))
    assert result.approved and not result.issues
    assert len(result.comparisons) == 2


@pytest.mark.parametrize('change', ['omitted', 'unknown', 'fake_location', 'no_condition', 'dismiss_fact'])
def test_invalid_or_nitpicking_blockers_cannot_be_accepted(change):
    conn, config = state()
    payload, finding = evidence()
    findings = [finding]
    if change == 'omitted': findings = []
    if change == 'unknown': finding['fact_id'] = 'not-a-fact'
    if change == 'fake_location': finding['generated_evidence'][0]['excerpt'] = 'nonexistent'
    if change == 'no_condition': finding['status'] = 'changed'
    if change == 'dismiss_fact': finding['status'] = 'non_behavioral_difference'
    with pytest.raises(ValueError):
        review_behavior(conn, config, profile(max_agent_task_retries=1), 'unit', payload,
            lambda *_: json.dumps(dict(findings=findings)))


def test_implementation_links_require_real_main_code_for_every_fact():
    payload, finding = evidence()
    specification = BehaviorSpecification.model_validate(payload['behavior_specification'])
    bundle = NativeUnitBundle(files=payload['generated_bundle']['files'])
    with pytest.raises(ValueError, match='every behavior fact'):
        validate_implementations(bundle, specification)
    bundle = NativeUnitBundle.model_validate(dict(files=payload['generated_bundle']['files'],
        behavior_implementations={finding['fact_id']: finding['generated_evidence']}))
    validate_implementations(bundle, specification)
    bundle.behavior_implementations[finding['fact_id']][0].excerpt = 'invented'
    with pytest.raises(ValueError, match='absent'):
        validate_implementations(bundle, specification)


def test_reviewer_can_find_a_material_behavior_omitted_by_extraction():
    conn, config = state()
    payload, finding = evidence()
    extra = dict(finding, fact_id=None, status='missing', trigger='Empty input',
                 consequence='Source emits an attribute but candidate omits it')
    extra['generated_evidence'] = []
    result, _ = review_behavior(conn, config, profile(), 'unit', payload,
        lambda *_: json.dumps(dict(findings=[finding, extra])))
    assert not result.approved and len(result.issues) == 1


def test_grounded_findings_feed_generation_correction_with_original_evidence():
    from runtime.behavior_conversion.revisions import generate_reviewed_bundle
    conn, config = state()
    original = source()
    calls = []
    fact_id = None
    path = 'src/main/java/com/company/generated/Mapper.java'
    def model(instruction, encoded):
        nonlocal fact_id
        data = json.loads(encoded)
        calls.append(data)
        title = data['schema']['title']
        if title == 'BehaviorSpecification':
            return json.dumps(dict(facts=[fact(original)], unresolved_questions=[]))
        if title == 'NativeUnitBundle':
            assert data['sources'] == [original]
            fact_id = data['behavior_specification']['facts'][0]['fact_id']
            corrected = bool(data.get('behavior_review_feedback'))
            prefix = 'xsi:nil' if corrected else 'alternate:nil'
            code = 'package com.company.generated; public class Mapper { public String emit() { return "' + prefix + '"; } }'
            return json.dumps(dict(files=[dict(path=path, content=code)],
                behavior_implementations={fact_id: [dict(path=path, excerpt=code)]}))
        assert title == 'BehaviorComparison'
        generated = data['generated_bundle']['files'][0]['content']
        corrected = '"xsi:nil"' in generated
        return json.dumps(dict(findings=[dict(fact_id=fact_id, status='matched' if corrected else 'changed',
            rationale='Compare explicit attribute spelling', trigger='Enabled null input',
            consequence='Different output attribute', source_evidence=[dict(identity=original['identity'],
                content_hash=original['content_hash'], excerpt=original['content'])],
            generated_evidence=[dict(path=path, excerpt=generated)])]))
    result, _, review, _ = generate_reviewed_bundle(conn, config, profile(), 'unit', 'unit', 'Generate native code',
        dict(schema_version='scoped-fixture', sources=[original]), lambda *_args, **_kwargs: None,
        lambda value: dict(generated_bundle=value.model_dump(mode='json')), model)
    assert review.approved and '"xsi:nil"' in result.files[0].content
    generation = [request for request in calls if request['schema']['title'] == 'NativeUnitBundle']
    assert len(generation) == 2
    assert generation[1]['behavior_review_feedback']['comparisons'][0]['status'] == 'changed'
    assert '"alternate:nil"' in generation[1]['previous_bundle']['files'][0]['content']
    before = len(calls)
    generate_reviewed_bundle(conn, config, profile(), 'unit', 'unit', 'Generate native code',
        dict(schema_version='scoped-fixture', sources=[original]), lambda *_args, **_kwargs: None,
        lambda value: dict(generated_bundle=value.model_dump(mode='json')),
        lambda *_: pytest.fail('Unchanged reviewed conversion was repeated'))
    assert len(calls) == before


def test_bounded_review_parts_keep_facts_sources_and_every_test_without_mutation():
    from copy import deepcopy
    from agents.behavior_conversion.behavior_extraction import COMPARE
    from models.behavior_comparison import BehaviorComparison
    from runtime.behavior_conversion.review_payload import review_requests
    payload, _ = evidence()
    tests = [dict(path=f'src/test/java/Test{number}.java', content='// test evidence\n' + 'x' * 18000)
             for number in range(5)]
    payload['generated_bundle']['files'].extend(tests)
    payload['unit'] = dict(sources=deepcopy(payload['sources']))
    original = deepcopy(payload)
    parts = review_requests(payload, COMPARE, BehaviorComparison.model_json_schema(), 60000)
    assert len(parts) > 1 and payload == original
    observed = []
    for part in parts:
        assert part['sources'] == payload['sources']
        assert part['behavior_specification'] == payload['behavior_specification']
        assert part['unit']['sources_ref'] == 'sources' and 'sources' not in part['unit']
        observed.extend(item['path'] for item in part['generated_bundle']['files'] if item['path'].startswith('src/test/'))
    assert sorted(observed) == sorted(item['path'] for item in tests)
