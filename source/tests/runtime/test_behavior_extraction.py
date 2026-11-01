"""Verify source grounding, bounded extraction, reuse and generation evidence handoff."""

import hashlib
import json

import pytest

from models.behavior_specification import BehaviorSpecification
from runtime.behavior_conversion.behavior_extraction import extract_behavior, attach_behavior_specification
from runtime.behavior_conversion.behavior_fact_validation import validate_specification
from tests.runtime.test_behavior_conversion import state, profile


def source(identity='original', content='if (enabled && (value == null || value.isEmpty())) emit("xsi:nil", "true");'):
    return dict(identity=identity, content=content, content_hash=hashlib.sha256(content.encode()).hexdigest())


def fact(evidence):
    return dict(behavior='Preserve conditional attributes', trigger='enabled and null or empty',
        outcome='Emit the source-specified attribute', evidence=[dict(
            identity=evidence['identity'], content_hash=evidence['content_hash'], excerpt=evidence['content'][:80])])


def extractor(calls):
    def model(instruction, encoded):
        data = json.loads(encoded)
        calls.append(data)
        if data['schema']['title'] == 'BehaviorReconciliation':
            return json.dumps(dict(conflicting_fact_ids=[], unresolved_questions=[]))
        evidence = next((s for s in data['sources'] if not s['identity'].startswith('compatibility-policy:')), data['sources'][0])
        item = fact(evidence)
        if evidence['identity'].startswith('compatibility-policy:'):
            item['origin'] = 'compatibility_policy'
        return json.dumps(dict(facts=[item], unresolved_questions=[]))
    return model


def test_extraction_retains_original_code_stable_facts_and_cache():
    conn, config = state()
    payload = dict(sources=[source()], configuration_xml='<Field/><Attribute/>')
    calls = []
    model = extractor(calls)
    result = attach_behavior_specification(conn, config, profile(), 'unit', payload, model)
    assert result['sources'] == payload['sources']
    assert result['behavior_specification']['facts'][0]['fact_id'].startswith('behavior-')
    assert all('generated_bundle' not in request for request in calls)
    again = attach_behavior_specification(conn, config, profile(), 'unit', payload,
        lambda *_: pytest.fail('Unchanged extraction was repeated'))
    assert again == result
    assert conn.execute("SELECT count(*) FROM behavior_snapshots WHERE category='behavior_specification'").fetchone()[0] == 1
    changed = dict(payload, sources=[source(content='if (enabled) emit("other", "value");')])
    updated = attach_behavior_specification(conn, config, profile(), 'unit', changed, model)
    assert updated['behavior_specification_fingerprint'] != result['behavior_specification_fingerprint']


@pytest.mark.parametrize('change', ['identity', 'content_hash', 'excerpt', 'policy'])
def test_fabricated_citations_and_policy_confusion_are_rejected(change):
    evidence = source()
    item = fact(evidence)
    if change == 'policy':
        item['origin'] = 'compatibility_policy'
    else:
        item['evidence'][0][change] = 'invented'
    with pytest.raises(ValueError):
        validate_specification(BehaviorSpecification(facts=[item]), [evidence])


def test_missing_evidence_blocks_before_generation():
    conn, config = state()
    with pytest.raises(ValueError, match='unresolved'):
        attach_behavior_specification(conn, config, profile(), 'unit', dict(sources=[source()]),
            lambda *_: json.dumps(dict(facts=[], unresolved_questions=['Missing formatter implementation'])))
    assert conn.execute("SELECT count(*) FROM behavior_attempts WHERE category='unit'").fetchone()[0] == 0


def test_large_evidence_is_split_without_losing_source_and_reconciled():
    conn, config = state()
    calls = []
    originals = [source('one', '// first\n' * 4500), source('two', '// second\n' * 4500)]
    result, _, _ = extract_behavior(conn, config, profile(behavior_context_chars=60000), 'unit',
                                    dict(sources=originals), extractor(calls))
    parts = [request for request in calls if request['schema']['title'] == 'BehaviorSpecification']
    assert len(parts) > 1
    for original in originals:
        pieces = [s['content'] for request in parts for s in request['sources'] if s['identity'] == original['identity']]
        assert ''.join(pieces) == original['content']
    assert calls[-1]['schema']['title'] == 'BehaviorReconciliation'
    assert result.facts


def test_lossy_summary_input_is_not_sufficient_for_extraction():
    conn, config = state()
    with pytest.raises(ValueError, match='original source'):
        extract_behavior(conn, config, profile(), 'unit', dict(source_summaries=[dict(summary='guessed')]),
                         lambda *_: pytest.fail('Lossy evidence was sent'))


def test_changed_compatibility_policy_invalidates_extraction(monkeypatch):
    import runtime.behavior_conversion.behavior_extraction as extraction
    conn, config = state()
    calls = []
    payload = dict(sources=[source()])
    first, fingerprint, _ = extract_behavior(conn, config, profile(), 'unit', payload, extractor(calls))
    monkeypatch.setattr(extraction, 'POLICY', extraction.POLICY + '\nAdditional agreed output requirement.')
    second, changed, _ = extract_behavior(conn, config, profile(), 'unit', payload, extractor(calls))
    assert fingerprint != changed and len(calls) == 2
    assert first.facts == second.facts


def test_explicit_versioned_requirements_are_supplied_as_policy_not_invented_source():
    from models.conversion_requirement import ConversionRequirement
    conn, config = state()
    calls = []
    settings = profile(conversion_requirements=[ConversionRequirement(requirement_id='wire-spelling',
        version=2, description='Preserve explicit source attribute spelling', applies_to=['response_format'])])
    _, _, sources = extract_behavior(conn, config, settings, 'unit',
        dict(kind='response_format', sources=[source()]), extractor(calls))
    assert calls[0]['subject_scope']['agreed_behavior_requirements']['wire-spelling']['version'] == 2
    policy = next(item for item in sources if item['identity'].startswith('compatibility-policy:'))
    assert 'Preserve explicit source attribute spelling' in policy['content']


def test_scoped_assembly_receives_revision_checked_xml_and_java_even_with_registered_alias(tmp_path):
    from types import SimpleNamespace
    from models.behavior_unit import SourceEvidence
    from runtime.behavior_conversion.service_flow import service_request
    path = tmp_path / 'operation.xml'
    path.write_text('<XML><CCDSEServerOperation id="Original"><opStep id="Work"/></CCDSEServerOperation></XML>')
    revision = hashlib.sha256(path.read_bytes()).hexdigest()
    workflow = dict(operation_id='RegisteredAlias', operation_attributes={'id': 'Original'}, requirements={},
        operation_source=dict(source_relative_path='operation.xml', source_hash=revision,
                              source_selector='/XML[1]/CCDSEServerOperation[1]'))
    settings = SimpleNamespace(source_root=str(tmp_path), java_version=25)
    code = SourceEvidence(**source())
    closure = dict(operation_id='RegisteredAlias', scoped_workflow=workflow)
    request = service_request(settings, closure, None, {},
                              source_units=[SimpleNamespace(sources=[code])])
    assert 'id="Original"' in request['configuration_xml']
    assert request['operation_sources'] == [code.model_dump(mode='json')]
    path.write_text(path.read_text().replace('Original', 'Changed'))
    with pytest.raises(ValueError, match='revision differs'):
        service_request(settings, closure, None, {}, source_units=[])
