"""Unit ladder retries technical failures, bypasses AI facts/review, and protects publication."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.revisions import generate_reviewed_bundle
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete
from runtime.behavior_conversion.verification_ladder import active_verification
from runtime.behavior_conversion.verification_binding import validate_binding
from runtime.behavior_conversion.bundle_output import accept_bundle
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.behavior_units import snapshot
from test_behavior_verification_boundaries import boundary_tool, source, unit
from test_typed_boundary_adapter import ROOT


def payload():
    result = unit(sources=[source('context', (ROOT / 'com/ibm/dse/base/Context.java').read_text()),
        source('work', '''package example; public class Work {
            public void setContext(com.ibm.dse.base.Context context) {} public int execute(){return 7;}
        }''')])
    result.update(schema_version='scoped-test-v1', requirements={}, evidence_ids=['unit-configured_step'])
    return result


def response(data, result=7):
    path = 'src/main/java/nativefixture/Work.java'
    return NativeUnitBundle(files=[dict(path=path, content='package nativefixture; public class Work { public int run(){return '+str(result)+';} }')],
        unit_contract=dict(unit_id=data['unit_id'], apis=[dict(type_name='nativefixture.Work', method_signatures=['public int run()'])],
            requirements={'business': 'return source value'}, evidence_ids=data['evidence_ids']),
        checklist_answers=dict(unit_id=data['unit_id'], source_manifest_hash=data['boundary']['source_manifest_hash'],
            configuration_hash=data['boundary']['configuration_hash'], responses=[dict(checklist_id=item['id'], status='implemented',
                locations=[dict(path=path, excerpt='return '+str(result)+';')]) for item in data['checklist']['items']]),
        verification_binding=dict(owner_type='nativefixture.Work', method_name='run'))


def state(tmp_path):
    conn = get_connection(':memory:'); create_all_tables(conn); upsert_run(conn, run_id='ladder', run_mode='full_inventory')
    return conn, SimpleNamespace(run_id='ladder', output_root=str(tmp_path)), PipelineConfiguration(
        model_provider='mock', conversion_strategy='behavior_units', max_agent_task_retries=2)


@pytest.mark.parametrize('triage', [False, True])
def test_concrete_boundary_failure_retries_and_never_uses_ai_review_as_gate(boundary_tool, tmp_path, triage):
    conn, config, profile = state(tmp_path)
    requests = []
    triage_requests = []
    profile.behavior_triage_enabled = triage
    def model(instruction, encoded):
        data = json.loads(encoded)
        if data['schema']['title'] == 'BehaviorReview':
            triage_requests.append(data)
            return json.dumps(dict(approved=False, issues=['Advisory review disagrees'], unresolved_questions=[]))
        requests.append(data)
        assert data['schema']['title'] == 'NativeUnitBundle'
        assert 'behavior_specification' not in data and data['slice_sources'] and 'checklist' in data
        return response(data, 8 if len(requests) == 1 else 7).model_dump_json()
    def validator(bundle, cached=False):
        session = active_verification(); session.static(bundle)
        project = tmp_path / ('candidate-' + str(len(requests))); project.mkdir(exist_ok=True)
        for file in bundle.files:
            path = project / file.path; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(file.content)
        session.compare(project, SimpleNamespace(), bundle, build_validation=dict(build_passed=True, tests_passed=True,
            test_count=1, issues=[], fixture='synthetic attestation; scoped integration separately runs real Maven/JUnit'))
    output, _, review, _ = generate_reviewed_bundle(conn, config, profile, 'unit', 'unit-configured_step', 'Convert',
        payload(), validator, lambda _: pytest.fail('AI review must not run'), model_call=model)
    assert len(requests) == 2 and review.approved
    assert bool(triage_requests) == triage
    assert requests[1]['verification_feedback']['failing_cases'][0]['differences']
    assert snapshot(conn, 'ladder', 'unit_verification', 'unit-configured_step')['status'] == 'accepted'
    # This component validator deliberately has no Maven POM. Advisory measurement failure cannot undo acceptance.
    assert snapshot(conn, 'ladder', 'unit_test_strength', 'unit-configured_step')['status'] == 'tool_error'
    from runtime.behavior_conversion.verification_state import require_unit_receipts
    import hashlib
    binding = dict(unit_id='unit-configured_step', files={file.path:hashlib.sha256(file.content.encode()).hexdigest() for file in output.files})
    require_unit_receipts(conn, config, dict(bindings={'step':binding}))
    from tools.behavior_verification.pilot_selection import select_pilot
    from tools.behavior_verification.pilot_measurement import measure_pilot
    original=payload()
    plan=select_pilot(dict(operations={'XML/Work':dict(units=[original])}),
        dict(boundaries={original['unit_id']:requests[0]['boundary']}),dataset_type='bank_demo',per_group=1)
    measured=measure_pilot(conn,plan,run_id='ladder',output_root=str(tmp_path))
    assert measured['rates']['accepted']['percent']==100 and not measured['production_pilot_completed']
    receipt = json.loads(snapshot(conn, 'ladder', 'unit_verification', 'unit-configured_step')['data_json'])
    evidence = Path(receipt['evidence']) / 'comparison/boundary-comparison.json'
    evidence.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='evidence changed'):
        require_unit_receipts(conn, config, dict(bindings={'step':binding}))
    measured=measure_pilot(conn,plan,run_id='ladder',output_root=str(tmp_path))
    assert measured['counts']=={'unverified_evidence':1} and measured['rates']['accepted']['percent']==0
    assert conn.execute("SELECT count(*) FROM behavior_attempts WHERE category='behavior_extraction'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM behavior_attempts WHERE category='review'").fetchone()[0] == int(triage)
    conn.close()


def test_incomplete_capability_does_not_consume_repeated_model_attempts(boundary_tool, tmp_path):
    conn, config, profile = state(tmp_path)
    calls = []
    def model(_, encoded):
        data = json.loads(encoded); calls.append(data); return response(data).model_dump_json()
    def validator(bundle, cached=False):
        raise VerificationIncomplete(dict(stage='harness', errors=['Unsupported external replay adapter']))
    with pytest.raises(VerificationIncomplete):
        generate_reviewed_bundle(conn, config, profile, 'unit', 'unit-configured_step', 'Convert', payload(),
                                 validator, lambda _: None, model_call=model)
    assert len(calls) == 1
    assert snapshot(conn, 'ladder', 'unit', 'unit-configured_step')['status'] == 'failed'
    conn.close()


def test_failed_prepublication_check_leaves_existing_project_unchanged(tmp_path):
    from runtime.behavior_conversion import validation
    from unittest.mock import patch
    project = tmp_path / 'project'; project.mkdir(); (project / 'pom.xml').write_text('<project/>')
    original = (project / 'pom.xml').read_bytes()
    def factory(profile, staged, name):
        return SimpleNamespace(pom_path=staged / 'pom.xml', verifier=lambda _: None, allowed_ibm_artifacts=[])
    def reject(staged, context, result): raise VerificationFailure(dict(stage='boundary', errors=['Observed mismatch']))
    with patch.object(validation, 'build_candidate', return_value=SimpleNamespace(issues=[])):
        with pytest.raises(VerificationFailure):
            accept_bundle(project, {'src/main/java/nativefixture/Work.java': 'package nativefixture; public class Work {}'},
                factory, SimpleNamespace(), [], require_tests=False, pre_publish=reject)
    assert not (project / 'src').exists() and (project / 'pom.xml').read_bytes() == original


def test_declarative_binding_rejects_jdk_objects_and_executable_harness_sources():
    from models.native_boundary_value import NativeBoundaryValue
    # Actual public native API required even when a valid-looking class name is provided.
    item = NativeUnitBundle(files=[dict(path='src/main/java/nativefixture/Work.java', content='package nativefixture; public class Work { public int run(){return 7;} }')],
        unit_contract=dict(unit_id='u', apis=[dict(type_name='nativefixture.Work')], requirements={'business':'x'}, evidence_ids=['u']),
        verification_binding=dict(owner_type='nativefixture.Work', method_name='run', arguments=[
            dict(type_name='java.io.File', source='object')]))
    with pytest.raises(VerificationFailure): validate_binding(item)


def test_packaging_rejects_fact_only_acceptance_and_boolean_claims(tmp_path):
    from runtime.behavior_conversion.verification_state import require_unit_receipts, record_verification
    conn, config, _ = state(tmp_path)
    record = dict(bindings={'step': dict(unit_id='u', files={'src/main/java/example/Work.java': 'hash'})})
    with pytest.raises(ValueError, match='lacks technical'):
        require_unit_receipts(conn, config, record)
    with pytest.raises(ValueError, match='evidence changed'):
        record_verification(conn, config, 'u', 'accepted', dict(approved=True))
    conn.close()
