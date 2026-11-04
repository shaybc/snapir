"""Keep fixture corrections separate from Java changes and preserve the test contract."""
import json
import sqlite3
from types import SimpleNamespace
import pytest
from models.junit_test_scenario import JunitScenarioSuite
from models.native_test_bundle import NativeTestBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.test_assets.preparation_feedback import load_feedback,retain_feedback,prepare_review,tests_for_manifest as manifest_tasks
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.state_store_tools import staged_conversion_state as state,behavior_units


def setup():
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    state.initialize(conn);behavior_units.initialize(conn)
    tasks=SimpleNamespace(conn=conn,config=SimpleNamespace(run_id='run'),identity='component',revision='revision',
        profile=PipelineConfiguration(),model_call=lambda *args:None,validator=None,label='component',category=None,payload=None)
    suite=JunitScenarioSuite(scenarios=[dict(scenario_id='configured',purpose='Keep the expected configured result',
        native_entry=dict(owner_type='nativecode.Format',method_name='format'),assertions=['expected configured tag'])])
    return tasks,suite


def test_reported_setup_issue_routes_to_preparation_and_preserves_assertions():
    tasks,suite=setup();production=[dict(path='src/main/java/nativecode/Format.java',content='class Format {}')]
    request=dict(production_files=production,junit_scenarios=suite.model_dump(mode='json'))
    attempt=state.reserve(tasks.conn,'run','component','revision','tests',4,request)
    result=NativeTestBundle(files=[dict(path='src/test/java/FormatTest.java',content='class FormatTest {}')],unresolved_questions=['Receiver configuration is missing'])
    state.finish(tasks.conn,'run','component','revision','tests',attempt,response=result.model_dump_json(),error='Tests-only stage has unresolved setup')
    feedback=load_feedback(tasks,production)
    assert feedback['round']==1 and feedback['errors']==result.unresolved_questions
    behavior_units.save(tasks.conn,'run','staged_junit_scenarios','component:revision','old',suite.model_dump(mode='json'))
    request,check=prepare_review(tasks,{},feedback,lambda value:None)
    assert behavior_units.snapshot(tasks.conn,'run','staged_junit_scenarios','component:revision')['status']=='verification_incomplete'
    assert request['preparation_feedback']['retained_scenarios']['scenarios'][0]['assertions']==['expected configured tag']
    corrected=suite.model_copy(deep=True)
    from models.native_boundary_value import NativeBoundaryValue
    corrected.scenarios[0].native_entry.constructor_arguments=[NativeBoundaryValue(type_name='java.lang.String',source='fixture',key='tag')]
    check(corrected)
    corrected.scenarios[0].assertions=['expect accidental default']
    with pytest.raises(ValueError,match='preserve retained'):check(corrected)
    with pytest.raises(ValueError,match='Unchanged preparation'):check(suite)


def test_preparation_reviews_are_bounded_without_resetting_test_attempts():
    tasks,suite=setup()
    for _ in range(4):retain_feedback(tasks,['review setup'],suite)
    with pytest.raises(VerificationIncomplete,match='Bounded preparation correction limit'):retain_feedback(tasks,['review setup'],suite)
    assert json.loads(state.read(tasks.conn,'run','component','revision','preparation_feedback')['artifact_json'])['round']==4
    assert state.read(tasks.conn,'run','component','revision','tests')['attempts']==0


def test_tests_budget_identity_is_bound_to_the_immutable_fixture_manifest():
    tasks,_=setup()
    first=manifest_tasks(tasks,'first');same=manifest_tasks(tasks,'first');second=manifest_tasks(tasks,'second')
    assert first.revision==same.revision and first.revision!=second.revision
    assert first.identity==tasks.identity and first.payload==tasks.payload


def test_fixture_setup_review_keeps_data_while_ai_reassesses_capabilities():
    from models.shared_test_fixture import SharedFixtureBank
    from runtime.test_assets.preparation_feedback import fixture_review
    bank=SharedFixtureBank(fixtures={'items':dict(value=['original'])},unresolved=['Collection setup unavailable'])
    checked=[]
    request,check=fixture_review({'source':'original'},bank,{'errors':['Review supported collection recipe']},lambda value:checked.append(value))
    assert request['preparation_feedback']['retained_fixture_bank']==bank.model_dump(mode='json')
    corrected=bank.model_copy(deep=True);corrected.unresolved=[];check(corrected)
    assert checked==[corrected] and bank.unresolved
    corrected.fixtures['items'].value=['different']
    with pytest.raises(ValueError,match='preserve retained data'):check(corrected)
