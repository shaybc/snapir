"""Verify that Gate 4 prevents microservice side effects until current evidence is approved."""
import json
import yaml
from pathlib import Path

import pytest

from models.maven_dependency import MavenDependency
from models.pipeline_configuration import PipelineConfiguration
from runtime.human_gates import record_decision
from runtime.workspace_paths import run_report_path
from tests.runtime.test_service_generation import ready, run, wrappers


def prepared(tmp_path):
    setup=ready(tmp_path)
    from tools.workspace_intake_tools.run_factory import persist_run_config
    persist_run_config(setup[0],setup[1])
    setup[2].microservice.enabled=True
    return setup


def forbid_creation(monkeypatch):
    monkeypatch.setattr('runtime.service_generation.shared_runtime.install_runtime',
        lambda *args:pytest.fail('Shared runtime build started before Gate 4 approval'))


def test_microservices_default_on_and_old_policy_snapshots_get_human_gate_four():
    profile=PipelineConfiguration(gate_policies={str(n):'automatic' for n in range(1,4)})
    assert profile.microservice.enabled
    assert profile.gate_policies['4']=='human'
    assert not PipelineConfiguration(microservice={'enabled':False}).microservice.enabled
    assert PipelineConfiguration(gate_policies={'4':'automatic'}).gate_policies['4']=='automatic'


def test_gate_three_approval_does_not_start_microservice_creation(tmp_path,monkeypatch):
    setup=prepared(tmp_path);forbid_creation(monkeypatch)
    assert run(tmp_path,setup,generator=lambda _:pytest.fail('Model generation started'))=='gate_4_pending'
    conn,config,profile,plan,_=setup
    assert conn.execute('SELECT current_phase FROM runs').fetchone()[0]=='gate_4_pending'
    assert conn.execute('SELECT COUNT(*) FROM service_generation_checkpoints').fetchone()[0]==0
    assert not (tmp_path/'services').exists() and not (tmp_path/'shared-runtime').exists()
    assert (Path(config.output_root)/'INTERNET/Op/values.yaml').exists()
    report=run_report_path(tmp_path,'gate_4_report.txt')
    assert report.parent.name=='6_service_generation_and_validation'
    assert 'INTERNET/Op' in report.read_text()


def test_rejection_is_durable_and_creates_nothing(tmp_path,monkeypatch):
    setup=prepared(tmp_path);forbid_creation(monkeypatch)
    assert run(tmp_path,setup)=='gate_4_pending'
    report=run_report_path(tmp_path,'gate_4_report.txt').read_text()
    record_decision(setup[0],setup[1].run_id,4,report,'rejected')
    assert run(tmp_path,setup)=='gate_4_rejected'
    assert run(tmp_path,setup)=='gate_4_rejected'
    assert not (tmp_path/'services').exists()


def test_approval_allows_generation_and_semantic_preview_keeps_approval_current(tmp_path,monkeypatch):
    setup=prepared(tmp_path)
    calls=[]
    dependency=MavenDependency(group_id='il.co.dcd',artifact_id='native-integration-runtime',
        version='1.0.0',reason='Explicit offline gate-test runtime fixture')
    monkeypatch.setattr('runtime.service_generation.shared_runtime.install_runtime',
        lambda *args:(calls.append('runtime') or dependency,{'build_passed':True}))
    monkeypatch.setattr('runtime.service_generation.microservice_output.package_microservice',
        lambda *args,**kwargs:calls.append('helm') or {'packaging_passed':True})
    def generate(payload):
        calls.append('generate')
        output=wrappers(payload)
        output['files'].pop('src/main/resources/application.properties')
        output['files']['src/main/resources/initialization-bindings.json']='{"consumed_keys":[]}'
        return output
    assert run(tmp_path,setup,generate)=='gate_4_pending'
    assert calls==[]
    report=run_report_path(tmp_path,'gate_4_report.txt').read_text()
    record_decision(setup[0],setup[1].run_id,4,report,'approved')
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    assert calls==['runtime','generate','helm']
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    assert calls==['runtime','generate','helm','runtime','helm']
    assert run_report_path(tmp_path,'gate_4_report.txt').read_text()==report
    # A deployment change requires a fresh decision before another generation or build.
    path=Path(setup[1].output_root)/'INTERNET/Op/values.yaml'
    definition=yaml.safe_load(path.read_text());definition['http']['path']='/changed'
    path.write_text(yaml.safe_dump(definition))
    assert run(tmp_path,setup,generate)=='gate_4_pending'
    assert calls.count('generate')==1 and calls.count('runtime')==2


def test_changed_generation_settings_require_new_approval(tmp_path,monkeypatch):
    setup=prepared(tmp_path);forbid_creation(monkeypatch)
    assert run(tmp_path,setup)=='gate_4_pending'
    report=run_report_path(tmp_path,'gate_4_report.txt').read_text()
    record_decision(setup[0],setup[1].run_id,4,report,'approved')
    setup[2].microservice.helm_executable='different-helm'
    assert run(tmp_path,setup)=='gate_4_pending'
    assert run_report_path(tmp_path,'gate_4_report.txt').read_text()!=report


def test_failed_native_checks_cannot_be_approved_automatically(tmp_path):
    from runtime.service_generation.gate import require_microservice_approval
    setup=prepared(tmp_path);setup[2].gate_policies['4']='automatic'
    item=dict(channel='INTERNET',operation_id='Op',fingerprint='native',issues=['Source evidence is stale'])
    assert require_microservice_approval(setup[0],setup[1],setup[2],tmp_path,[item],
        approved_report='upstream',settings_identity='settings')=='gate_4_blocked'
    assert not setup[0].execute('SELECT 1 FROM runtime_gate_decisions WHERE gate_number=4').fetchone()


def test_gate_four_approval_is_operation_scoped(tmp_path):
    from runtime.human_gates import operation_gate_scope
    from runtime.operation_review.evidence import collect_operation_evidence
    from runtime.service_generation.gate import require_microservice_approval
    setup=prepared(tmp_path);conn,config,profile,plan,_=setup
    items=collect_operation_evidence(conn,config,profile,plan)
    def check():
        return require_microservice_approval(conn,config,profile,tmp_path,items,
            approved_report='upstream',settings_identity='settings')
    with operation_gate_scope('INTERNET/Op'):
        assert check()=='gate_4_pending'
        record_decision(conn,config.run_id,4,run_report_path(tmp_path,'gate_4_report.txt').read_text(),'approved')
        assert check()=='approved'
    with operation_gate_scope('INTERNET/OtherOp'):
        assert check()=='gate_4_pending'


def test_saved_gate_four_can_resume_through_the_existing_runtime(tmp_path,monkeypatch):
    import sqlite3
    from contextlib import nullcontext
    from runtime.checkpoints import resume_pipeline
    from tools.state_store_tools.runs import update_run_status
    directory=tmp_path/'run-1';directory.mkdir()
    setup=prepared(directory);conn,config,profile,plan,_=setup
    from agents.migration_planning.agent import write_migration_plan
    write_migration_plan(conn,plan)
    update_run_status(conn,config.run_id,'paused','gate_4_pending')
    state=directory/'state';state.mkdir()
    with sqlite3.connect(state/'migration.db') as saved:conn.backup(saved)
    (state/'profile.json').write_text(profile.model_dump_json(),encoding='utf-8')
    monkeypatch.setattr('runtime.checkpoints.java_scope',lambda _:nullcontext())
    monkeypatch.setattr('runtime.component_review.run_component_review_gate',lambda *a,**k:'assembly_pending')
    monkeypatch.setattr('runtime.operation_assembly.run_operation_assembly',lambda *a,**k:'operation_review_pending')
    monkeypatch.setattr('runtime.operation_review.run_operation_review_gate',lambda *a,**k:'service_generation_pending')
    calls=[]
    monkeypatch.setattr('runtime.service_generation.run_service_generation',
        lambda *a,**k:calls.append(a[1].run_id) or 'gate_4_pending')
    assert resume_pipeline(str(tmp_path),'run-1')==directory
    assert calls==['run-1']


def test_creation_gate_four_is_followed_by_final_gate_five(tmp_path,monkeypatch):
    from runtime.finalization import run_finalization
    setup=prepared(tmp_path);conn,config,profile,plan,_=setup
    profile.executable_verification.mode='conversion_checklist_v1'
    dependency=MavenDependency(group_id='il.co.dcd',artifact_id='native-integration-runtime',
        version='1.0.0',reason='Offline approval-flow fixture')
    monkeypatch.setattr('runtime.service_generation.shared_runtime.install_runtime',lambda *a:(dependency,{'build_passed':True}))
    def package(project,*args,**kwargs):
        (project/'helm/chart').mkdir(parents=True)
        (project/'helm/chart/Chart.yaml').write_text('apiVersion: v2\nname: chart\nversion: 1.0.0\n')
        (project/'Dockerfile').write_text('FROM fixture')
        (project/'deployment-readiness.json').write_text('{"deployment_ready":false}')
        return {'packaging_passed':True}
    monkeypatch.setattr('runtime.service_generation.microservice_output.package_microservice',package)
    def generate(payload):
        output=wrappers(payload);output['files'].pop('src/main/resources/application.properties')
        output['files']['src/main/resources/initialization-bindings.json']='{"consumed_keys":[]}'
        return output
    assert run(tmp_path,setup,generate)=='gate_4_pending'
    assert (Path(config.output_root)/'INTERNET/Op/values.yaml').exists()
    record_decision(conn,config.run_id,4,run_report_path(tmp_path,'gate_4_report.txt').read_text(),'approved')
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    assert run_finalization(conn,config,profile,plan,tmp_path)=='gate_5_pending'
    report=run_report_path(tmp_path,'gate_5_report.txt').read_text()
    assert report.startswith('=== Human Gate 5 ===')
    record_decision(conn,config.run_id,5,report,'approved')
    assert run_finalization(conn,config,profile,plan,tmp_path)=='migration_approved'
