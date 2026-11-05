"""Sibling projects retain stable Maven identities, private sources and external audit paths."""
from pathlib import Path
from xml.etree import ElementTree
from models.pipeline_configuration import PipelineConfiguration
from runtime.operation_layout import standalone_project, service_root, application_project, service_artifacts, artifact_name
from runtime.service_generation.maven_reactor import prepare_reactor, reactor_hash
from runtime.behavior_conversion.standalone_runner import write_standalone_runner
from types import SimpleNamespace
import json
import sqlite3
import pytest
from runtime.operation_state_relocation import rebind_current_artifacts
from tools.conversion_tools.scoped_reuse.fingerprints import digest, revision


def test_every_new_operation_gets_qualified_sibling_projects(tmp_path):
    for channel, operation in [('INTERNET', 'FirstOp'), ('SME', 'SecondOp')]:
        native = standalone_project(tmp_path/'generated', channel, operation)
        assert native == tmp_path/'generated'/channel/operation/'standalone'
        native.mkdir(parents=True)
        (native/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>'+operation+'</artifactId></project>')
        root=service_root(tmp_path,dict(project=native,channel=channel,operation_id=operation))
        assert root==native.parent/'microservice'
        assert artifact_name(native)==operation
        assert not root.exists()  # Assembly does not create a microservice before Gate 4.
        write_standalone_runner(native,tmp_path/'generated',SimpleNamespace(service_api=SimpleNamespace(type_name=operation)))
        assert (native/'run-operation.bat').exists() and (native.parent/'package-standalone-operation.bat').exists()


def test_reactor_includes_private_sources_and_hashes_them_without_build_cache(tmp_path):
    root=tmp_path/'generated/INTERNET/Example/microservice'
    app=prepare_reactor(root,PipelineConfiguration())
    assert app==root/'application'
    (app/'pom.xml').write_text('<project/>')
    assert application_project(root)==app
    modules=ElementTree.parse(root/'pom.xml').findall('{*}modules/{*}module')
    assert [m.text for m in modules]==['integration-runtime','test-support','application']
    for module in ['integration-runtime','test-support']:
        assert (root/module/'pom.xml').is_file() and list((root/module/'src/main/java').rglob('*.java'))
        assert not (root/module/'target').exists()
    expected=reactor_hash(root)
    target=app/'target';target.mkdir();(target/'cache.log').write_text('not a build input')
    assert reactor_hash(root)==expected
    source=next((root/'integration-runtime/src/main/java').rglob('*.java'))
    source.write_bytes(source.read_bytes()+b'\n')
    assert reactor_hash(root)!=expected
    assert service_artifacts(root)==tmp_path/'generated/.converter-operations/INTERNET/Example/microservice'


def test_legacy_projects_remain_readable_until_explicit_migration(tmp_path):
    project=tmp_path/'INTERNET/OldOp';project.mkdir(parents=True);(project/'pom.xml').write_text('<project/>')
    assert standalone_project(tmp_path,'INTERNET','OldOp')==project
    assert service_root(tmp_path,dict(project=project,channel='INTERNET',operation_id='OldOp'))==tmp_path/'services/INTERNET/OldOp'


@pytest.mark.parametrize('tampered',[False,True])
def test_relocation_preserves_scoped_integrity_and_rejects_changed_bytes(tmp_path,tampered):
    old=tmp_path/'Old';new=tmp_path/'New';old.mkdir();new.mkdir()
    source=old/'Code.java';source.write_bytes(b'approved bytes\r\n')
    expected=revision(source);(new/'Code.java').write_bytes(source.read_bytes() if not tampered else b'changed')
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE behavior_snapshots(run_id TEXT,category TEXT,identity TEXT,data_json TEXT)')
    c.execute('CREATE TABLE scoped_reuse_entries(run_id TEXT,category TEXT,identity TEXT,fingerprint TEXT,data_json TEXT,data_hash TEXT,files_json TEXT)')
    data={'project':str(old),'files':{'Code.java':expected}}
    files={str(source):expected}
    c.execute('INSERT INTO behavior_snapshots VALUES(?,?,?,?)',('run','operation','INTERNET/Op',json.dumps(data)))
    c.execute('INSERT INTO scoped_reuse_entries VALUES(?,?,?,?,?,?,?)',('run','native_artifact','key','source-fingerprint',json.dumps(data),digest(dict(data=data,files=files)),json.dumps(files)))
    c.commit();c.execute('SAVEPOINT move')
    if tampered:
        with pytest.raises(ValueError,match='bytes differ'):rebind_current_artifacts(c,'run',[(old,new)])
        c.execute('ROLLBACK TO SAVEPOINT move')
        assert json.loads(c.execute('SELECT data_json FROM behavior_snapshots').fetchone()[0])==data
    else:
        changed=rebind_current_artifacts(c,'run',[(old,new)])
        row=c.execute('SELECT * FROM scoped_reuse_entries').fetchone()
        actual=dict(data=json.loads(row['data_json']),files=json.loads(row['files_json']))
        assert row['data_hash']==digest(actual) and actual['files']=={str(new/'Code.java'):expected}
        assert row['fingerprint']=='source-fingerprint'
        assert changed=={'behavior_snapshots':1,'scoped_reuse_entries':1}
        assert c.execute('SELECT count(*) FROM artifact_location_migrations').fetchone()[0]==2
    c.close()


def test_migration_retains_locked_original_and_rebinds_only_verified_copy(tmp_path,monkeypatch):
    from runtime.operation_layout_migration import migrate_operation,source_inventory
    run=tmp_path/'run';native=run/'generated/INTERNET/Example';service=run/'services/INTERNET/Example'
    for project in [native,service]:
        (project/'src/main/java').mkdir(parents=True)
        (project/'pom.xml').write_text('<project/>')
        (project/'src/main/java/Example.java').write_bytes(b'class Example {}\r\n')
    (native/'standalone').mkdir()
    (native/'standalone/operation.json').write_text(json.dumps(dict(service_class='Example',runtime_config='../runtime-config.json')))
    (native/'runtime-config.json').write_text('{}')
    expected=source_inventory(service)
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.executescript("CREATE TABLE runs(run_id TEXT,status TEXT);INSERT INTO runs VALUES('run','paused');"
        "CREATE TABLE generated_artifacts(run_id TEXT,artifact_kind TEXT,generated_path TEXT);"
        "CREATE TABLE behavior_snapshots(run_id TEXT,category TEXT,identity TEXT,data_json TEXT);"
        "CREATE TABLE scoped_reuse_entries(run_id TEXT,category TEXT,identity TEXT,fingerprint TEXT,data_json TEXT,data_hash TEXT,files_json TEXT);")
    c.execute('INSERT INTO generated_artifacts VALUES(?,?,?)',('run','service',str(service)));c.commit()
    original=Path.rename
    def locked(path,target):
        if path==service:raise PermissionError('Directory is held by Windows')
        return original(path,target)
    monkeypatch.setattr(Path,'rename',locked)
    monkeypatch.setattr('runtime.behavior_conversion.standalone_runner.write_standalone_runner',lambda *a:None)
    monkeypatch.setattr('runtime.fixture_demo.preparation.prepare_operation_demo',lambda *a:dict(status='prepared'))
    result=migrate_operation(c,SimpleNamespace(output_root=run/'generated',run_id='run'),'INTERNET','Example',run,tmp_path/'audit')
    assert result['legacy_service_backup_retained'] and service.is_dir()
    assert source_inventory(native/'microservice/application')==source_inventory(service)==expected
    assert source_inventory(native/'standalone')==expected
    assert c.execute('SELECT generated_path FROM generated_artifacts').fetchone()[0]==str(native/'microservice')
    assert (tmp_path/'audit/before-layout.sqlite').exists()
    c.close()


def test_new_service_stage_waits_for_gate_four_and_builds_sibling_reactor(tmp_path,monkeypatch):
    from tests.runtime.test_microservice_gate import prepared
    from tests.runtime.test_service_generation import run,wrappers
    from runtime.operation_review.evidence import collect_operation_evidence
    from runtime.human_gates import record_decision
    from runtime.workspace_paths import run_report_path
    from models.maven_dependency import MavenDependency
    setup=prepared(tmp_path);c,config,profile,plan,_=setup
    item=collect_operation_evidence(c,config,profile,plan)[0]
    old=Path(item['project']);holding=old.with_name('native-holding');old.rename(holding);old.mkdir()
    holding.rename(old/'standalone');item['project']=str(old/'standalone')
    monkeypatch.setattr('runtime.service_generation.runner.collect_operation_evidence',lambda *a:[dict(item)])
    calls=[]
    dependency=MavenDependency(group_id='il.co.dcd',artifact_id='native-integration-runtime',version='1.0.0',reason='Gate fixture')
    monkeypatch.setattr('runtime.service_generation.shared_runtime.install_runtime',lambda *a:(calls.append('runtime') or dependency,{}))
    monkeypatch.setattr('runtime.service_generation.maven_reactor.verify_reactor',lambda root,context:calls.append(('reactor',root)) or dict(passed=True))
    monkeypatch.setattr('runtime.service_generation.microservice_output.package_microservice',lambda root,*a,**kw:calls.append(('package',root)) or dict(packaging_passed=True))
    def generate(payload):
        output=wrappers(payload);output['files'].pop('src/main/resources/application.properties')
        output['files']['src/main/resources/initialization-bindings.json']='{"consumed_keys":[]}'
        calls.append('generate');return output
    root=old/'microservice'
    assert run(tmp_path,setup,generate)=='gate_4_pending'
    assert not calls and not root.exists()
    record_decision(c,config.run_id,4,run_report_path(tmp_path,'gate_4_report.txt').read_text(),'approved')
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    assert calls==['runtime','generate',('reactor',root),('package',root)]
    assert all((root/module/'pom.xml').exists() for module in ['application','integration-runtime','test-support'])
    assert not (tmp_path/'services').exists()
    for source in (old/'standalone/src/main/java').rglob('*.java'):
        assert source.read_bytes()==(root/'application'/source.relative_to(old/'standalone')).read_bytes()
    assert c.execute('SELECT COUNT(*) FROM runtime_gate_decisions WHERE gate_number=5 AND decision="approved"').fetchone()[0]==0


def test_nested_legacy_wrapper_mode_keeps_its_safe_retry_workspace(tmp_path,monkeypatch):
    from tests.runtime.test_service_generation import ready,run,wrappers
    from runtime.operation_review.evidence import collect_operation_evidence
    setup=ready(tmp_path);c,config,profile,plan,_=setup
    item=collect_operation_evidence(c,config,profile,plan)[0]
    old=Path(item['project']);holding=old.with_name('native-holding');old.rename(holding);old.mkdir()
    holding.rename(old/'standalone');item['project']=str(old/'standalone')
    monkeypatch.setattr('runtime.service_generation.runner.collect_operation_evidence',lambda *a:[dict(item)])
    calls=[]
    def generate(payload):calls.append(True);return wrappers(payload)
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    (old/'microservice/src/main/resources/application.properties').write_text('changed')
    assert run(tmp_path,setup,generate)=='validation_evidence_pending'
    assert len(calls)==2
