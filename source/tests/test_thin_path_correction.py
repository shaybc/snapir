"""Corrections use the retained Java and compared values, not unrelated tooling limitations."""
import hashlib
import json
import sqlite3
import pytest
from models.thin_path_comparison_report import ThinPathComparisonReport
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.thin_path_correction import seed_correction
from test_behavior_verification_boundaries import unit
from tests.runtime.test_behavior_conversion import bundle


@pytest.fixture
def correction(tmp_path):
    original=unit();candidate=bundle();database=tmp_path/'saved.db'
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE behavior_attempts(category TEXT,identity TEXT,attempt INTEGER,request_json TEXT,response TEXT)')
        conn.execute('INSERT INTO behavior_attempts VALUES(?,?,?,?,?)',('thin_path_experiment',original['unit_id'],3,
            json.dumps(dict(selected_unit={'fingerprint':original['fingerprint']},sources=original['sources'])),candidate.model_dump_json()))
    boundary=boundary_contract(original)
    report=ThinPathComparisonReport(unit_id=original['unit_id'],source_manifest_hash=boundary.source_manifest_hash,
        configuration_hash=boundary.configuration_hash,status='differences_found',limitations=[{'kind':'presence_not_observable'}],
        cases=[dict(case={'input_xml':'<R/>'},legacy={'status':'completed'},native={'status':'completed'},
            differences=[dict(path='context.Value',legacy=1,native=2,related_checklist_ids=['ignored'])])],
        artifact_hashes={'native:compiled_text:'+file.path:hashlib.sha256(file.content.encode()).hexdigest()
                        for file in candidate.files if file.path.startswith('src/main/java/')})
    path=tmp_path/'comparison.json';path.write_text(report.model_dump_json(),encoding='utf-8')
    return database,original,candidate,report,path


def test_seed_uses_exact_saved_candidate_and_only_compared_differences(correction):
    database,original,candidate,_,path=correction
    request,saved=seed_correction({'requirements':{'observed-boundary':'Compare'}},database,3,original,path)
    assert json.loads(request['previous_model_response'])==candidate.model_dump(mode='json')
    assert 'presence_not_observable' not in request['correction_feedback']
    assert 'ignored' not in request['correction_feedback']
    assert json.loads(request['correction_feedback'])['failing_cases'][0]['differences']==[
        dict(path='context.Value',legacy=1,native=2)]
    assert saved['attempt']==3


def test_correction_does_not_request_presence_machinery():
    from test_thin_path_experiment import preparation
    from tools.behavior_verification.thin_path_request import select_units,build_request
    from models.pipeline_configuration import PipelineConfiguration
    from types import SimpleNamespace
    original=select_units(preparation())[0]
    boundary=SimpleNamespace(unit_id=original['unit_id'],source_manifest_hash='source',configuration_hash='xml')
    _,instruction=build_request(original,boundary,[],PipelineConfiguration(java_version=25),correcting=True)
    assert 'do not add presence machinery' in instruction
    assert 'For new DTO outputs' not in instruction


@pytest.mark.parametrize('problem',['revision','candidate','tooling','unexecuted'])
def test_unrelated_or_unobservable_reports_cannot_seed_a_correction(correction,problem):
    database,original,_,report,path=correction
    if problem=='revision':report.configuration_hash='changed'
    if problem=='candidate':report.artifact_hashes={}
    if problem=='tooling':report.status='verification_incomplete'
    if problem=='unexecuted':report.cases[0]['native']['status']='verification_incomplete'
    path.write_text(report.model_dump_json(),encoding='utf-8')
    with pytest.raises(ValueError):seed_correction({},database,3,original,path)
