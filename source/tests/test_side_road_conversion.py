"""Exercise isolated baseline policy, persistent stage budgets and strict final validation."""
import json
from types import SimpleNamespace
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.side_road_policy import side_road_stage, ForbiddenFrameworkDependency
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.state_store_tools.side_road_state import load, reserve_attempt
from tests.runtime.test_behavior_conversion import state


def candidate(*, ibm=False, structured=False, changed_api=False):
    method='format' if not changed_api else 'changed'
    text='package example; '+('import com.ibm.dse.base.Context; ' if ibm else '')+(
        'public class Formatter { public String '+method+'(String value) { return value; } }')
    files=[dict(path='src/main/java/example/Formatter.java',content=text),
           dict(path='src/test/java/example/FormatterTest.java',content='package example; public class FormatterTest {}')]
    if structured:
        files.append(dict(path='src/main/java/example/Context.java',content='package example; public class Context {}'))
    files=[dict(path=file['path'].replace('/example/','/com/company/generated/example/'),
        content=file['content'].replace('package example;', 'package com.company.generated.example;')) for file in files]
    return NativeUnitBundle(files=files,coverage={'business':['src/test/java/com/company/generated/example/FormatterTest.java']},
        evidence_ids=['source'],unit_contract=dict(unit_id='unit',requirements={'business':'Preserve'},evidence_ids=['source'],
            apis=[dict(type_name='com.company.generated.example.Formatter',method_signatures=['public String '+method+'(String value)'])]),
        verification_binding=dict(owner_type='com.company.generated.example.Formatter',method_name=method,
            arguments=[dict(type_name='java.lang.String',source='context',key='Value')],output='result'))


class Validator:
    """Flow-only receipt fixture; this does not claim real Java compilation or equivalence."""
    def __init__(self, incomplete=False):
        self.stages=[]; self.final=[]; self.incomplete=incomplete

    def __call__(self,bundle,cached=False):
        validate_bundle(bundle,bundle.unit_contract.apis,['business'],['source'])
        self.final.append(bundle)

    def side_road_validate(self,bundle,stage):
        self.stages.append(stage)
        if self.incomplete:
            raise VerificationIncomplete(dict(stage='comparison',issues=['presence not observable']))
        return dict(status='matched_observed_cases',observed_cases=1,
            build_validation=dict(build_passed=True,tests_passed=True))


def payload():
    return dict(kind='response_format',requirements={'business':'Preserve'},
        sources=[dict(identity='source',content='complete original source')],configuration_xml='<fmtDef id="f"/>')


def run(conn,config,validator,model,**settings):
    return generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=False,side_road_conversion=True,
        max_agent_task_retries=1,**settings),'thin_path_experiment','unit','Normal conversion',payload(),
        NativeUnitBundle,validator=validator,model_call=model,require_coverage=False)


def test_temporary_structure_is_allowed_only_in_baseline_and_ibm_never_is():
    for stage in ['baseline','simplify']:
        with side_road_stage(stage):
            with pytest.raises(ForbiddenFrameworkDependency):validate_bundle(candidate(ibm=True))
    with side_road_stage('baseline'):
        validate_bundle(candidate(structured=True))
        with side_road_stage('simplify'):
            with pytest.raises(ValueError,match='recreate'):validate_bundle(candidate(structured=True))
        validate_bundle(candidate(structured=True))
    with pytest.raises(ValueError,match='recreate'):validate_bundle(candidate(structured=True))


def test_whole_unit_baseline_then_simplification_then_parent_checks():
    conn,config=state(); validator=Validator(); calls=[]
    def model(instruction,encoded):
        request=json.loads(encoded);stage=request.get('side_road_origin',{}).get('stage','normal');calls.append(stage)
        assert request['sources']==payload()['sources']
        if stage=='simplify':
            assert 'verified_baseline' in request
        return candidate(ibm=stage=='normal',structured=stage=='baseline').model_dump_json()
    try:
        result,_=run(conn,config,validator,model)
        assert calls==['normal','baseline','simplify']
        assert validator.stages==['baseline','simplify'] and len(validator.final)==1
        row=conn.execute('SELECT * FROM side_road_conversions').fetchone()
        assert row['status']=='simplified_verified' and row['baseline_attempts']==row['simplify_attempts']==1
        assert 'example/Context.java' in row['baseline_json']
        assert not any(f.path.endswith('/Context.java') for f in result.files)
        assert conn.execute("SELECT status FROM behavior_snapshots WHERE category='thin_path_experiment'").fetchone()[0]=='accepted'
    finally:conn.close()


def test_failed_simplification_keeps_baseline_and_never_resets_budget():
    conn,config=state();validator=Validator();calls=[]
    def model(instruction,encoded):
        stage=json.loads(encoded).get('side_road_origin',{}).get('stage','normal');calls.append(stage)
        return candidate(ibm=stage=='normal',structured=True).model_dump_json()
    try:
        with pytest.raises(ValueError):run(conn,config,validator,model)
        row=conn.execute('SELECT * FROM side_road_conversions').fetchone()
        assert row['status']=='baseline_available' and row['simplify_attempts']==4 and row['baseline_attempts']==1
        baseline=row['baseline_json']
        with pytest.raises(ValueError):run(conn,config,validator,model)
        row=conn.execute('SELECT * FROM side_road_conversions').fetchone()
        assert row['baseline_json']==baseline and row['simplify_attempts']==4
        assert calls.count('baseline')==1 and calls.count('simplify')==4
        assert not validator.final
    finally:conn.close()


def test_comparison_limitation_stops_without_correction_or_simplification():
    conn,config=state();validator=Validator(incomplete=True);calls=[]
    def model(instruction,encoded):
        stage=json.loads(encoded).get('side_road_origin',{}).get('stage','normal');calls.append(stage)
        return candidate(ibm=stage=='normal').model_dump_json()
    try:
        with pytest.raises(VerificationIncomplete):run(conn,config,validator,model)
        assert calls==['normal','baseline']
        assert conn.execute('SELECT baseline_json FROM side_road_conversions').fetchone()[0] is None
    finally:conn.close()


def test_stage_cannot_change_public_api():
    conn,config=state();validator=Validator()
    def model(instruction,encoded):
        stage=json.loads(encoded).get('side_road_origin',{}).get('stage','normal')
        return candidate(ibm=stage=='normal',changed_api=stage=='simplify').model_dump_json()
    try:
        with pytest.raises(ValueError,match='preserve verified public APIs'):run(conn,config,validator,model)
        assert not validator.final
    finally:conn.close()


def test_empty_validation_receipt_cannot_establish_baseline():
    conn,config=state();validator=Validator()
    validator.side_road_validate=lambda candidate,stage:{}
    calls=[]
    def model(instruction,encoded):
        stage=json.loads(encoded).get('side_road_origin',{}).get('stage','normal');calls.append(stage)
        return candidate(ibm=stage=='normal').model_dump_json()
    try:
        with pytest.raises(VerificationIncomplete,match='Missing verified'):run(conn,config,validator,model)
        assert calls==['normal','baseline']
        assert conn.execute('SELECT baseline_json FROM side_road_conversions').fetchone()[0] is None
    finally:conn.close()


def test_missing_isolated_adapter_never_relaxes_production_validation():
    conn,config=state()
    def validator(bundle,cached=False):validate_bundle(bundle)
    try:
        with pytest.raises(VerificationIncomplete,match='no isolated'):
            run(conn,config,validator,lambda *args:candidate(ibm=True).model_dump_json())
        assert conn.execute("SELECT count(*) FROM behavior_attempts").fetchone()[0]==1
    finally:conn.close()


def test_unverified_baseline_exhausts_its_own_budget_without_simplification():
    conn,config=state();validator=Validator();calls=[]
    def model(instruction,encoded):
        stage=json.loads(encoded).get('side_road_origin',{}).get('stage','normal');calls.append(stage)
        return candidate(ibm=True).model_dump_json()
    try:
        with pytest.raises(ForbiddenFrameworkDependency):run(conn,config,validator,model)
        assert calls.count('normal')==1 and calls.count('baseline')==4 and 'simplify' not in calls
        row=conn.execute('SELECT * FROM side_road_conversions').fetchone()
        assert row['baseline_json'] is None and row['status']=='blocked'
    finally:conn.close()


def test_normal_conversion_is_not_redirected_when_disabled():
    conn,config=state();calls=[]
    def model(*args):calls.append(True);return candidate(ibm=True).model_dump_json()
    try:
        with pytest.raises(ForbiddenFrameworkDependency):
            generate(conn,config,PipelineConfiguration(model_provider='mock',staged_unit_conversion=False,max_agent_task_retries=1),
                'thin_path_experiment','unit','Normal',payload(),NativeUnitBundle,validator=Validator(),
                model_call=model,require_coverage=False)
        assert len(calls)==1
    finally:conn.close()


def test_budget_is_persisted_across_database_reopen(tmp_path):
    import sqlite3
    database=tmp_path/'state.db'
    with sqlite3.connect(database) as conn:
        load(conn,'run','unit','revision')
        for _ in range(4):reserve_attempt(conn,'run','unit','revision','baseline',4)
    with sqlite3.connect(database) as conn:
        with pytest.raises(ValueError,match='budget exhausted'):reserve_attempt(conn,'run','unit','revision','baseline',4)
        assert load(conn,'run','unit','revision')['baseline_attempts']==4
        reserve_attempt(conn,'run','unit','revision','simplify',4)
