"""PIT strength is scoped, reproducible and advisory even when measurement fails."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
import pytest
from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from models.unit_mutation_settings import UnitMutationSettings
from tools.behavior_verification.mutation_snapshot import snapshot_project, NAMESPACE, PIT_VERSION
from tools.behavior_verification.mutation_results import read_mutations
from runtime.behavior_conversion.verification_test_strength import prepare_measurement, measure_accepted_unit


def candidate():
    return NativeUnitBundle(files=[
        dict(path='src/main/java/example/Balance.java',content='''package example;
public class Balance { public int available(int amount) { if(amount>0) return amount+1; return 0; } }'''),
        dict(path='src/test/java/example/BalanceTest.java',content='''package example;
public class BalanceTest { @org.junit.jupiter.api.Test public void positive(){
org.junit.jupiter.api.Assertions.assertTrue(new Balance().available(3)>0); } }''')],
        unit_contract=dict(unit_id='balance',apis=[dict(type_name='example.Balance',method_signatures=['public int available(int amount)'])],
                           requirements={'balance':'source behavior'},evidence_ids=['source']))


def project_at(root):
    project = root / 'original'; project.mkdir()
    (project / 'pom.xml').write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>example</groupId><artifactId>balance</artifactId><version>1</version>
<properties><maven.compiler.release>25</maven.compiler.release></properties>
<dependencies><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.11.4</version><scope>test</scope></dependency></dependencies>
<build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.14.1</version></plugin>
<plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.5.2</version></plugin></plugins></build></project>''')
    for file in candidate().files:
        p=project/file.path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(file.content)
    return project


def setup_measurement(tmp_path, enabled=True):
    project = project_at(tmp_path)
    session = SimpleNamespace(mutation_settings=UnitMutationSettings(enabled=enabled),attempt=tmp_path/'accepted-attempt',unit={'unit_id':'balance'})
    session.attempt.mkdir()
    prepare_measurement(session,project,candidate())
    receipt=dict(candidate_hash='accepted-revision',source_manifest_hash='original-source',configuration_hash='original-config')
    profile=PipelineConfiguration(java_version=25)
    return project, session, receipt, profile


def test_snapshot_limits_mutations_to_unit_files_and_preserves_original(tmp_path):
    project=project_at(tmp_path)
    before={str(p.relative_to(project)):p.read_bytes() for p in project.rglob('*') if p.is_file()}
    # An earlier unit's code and tests are available to compilation, but outside this unit's mutation scope.
    other=project/'src/main/java/example/BalanceOther.java'; other.write_text('package example; public class BalanceOther {}')
    report=snapshot_project(project,tmp_path/'copy',candidate())
    assert report['target_classes']==['example.Balance','example.Balance$*']
    assert report['target_tests']==['example.BalanceTest','example.BalanceTest$*']
    assert all((project/p).read_bytes()==content for p,content in before.items())
    assert report['files']['pom.xml']==hashlib.sha256(before['pom.xml']).hexdigest()
    root=ET.parse(tmp_path/'copy/pom.xml'); ns={'m':NAMESPACE}
    config=root.find('.//m:plugin[m:artifactId="pitest-maven"]/m:configuration',ns)
    assert config.findtext('m:mutationThreshold',namespaces=ns)=='0'
    assert config.findtext('m:reportsDirectory',namespaces=ns)==str((tmp_path/'pit-reports').resolve())


@pytest.mark.parametrize('statuses,status,score',[
    (['KILLED','SURVIVED','NO_COVERAGE'],'completed',33.33),
    (['KILLED','TIMED_OUT','RUN_ERROR'],'incomplete',100.0),([], 'no_mutations',None)])
def test_summary_does_not_call_timeouts_killed_or_no_mutations_perfect(tmp_path,statuses,status,score):
    root=ET.Element('mutations')
    for value in statuses: ET.SubElement(root,'mutation',status=value)
    path=tmp_path/'mutations.xml'; ET.ElementTree(root).write(path)
    report=read_mutations(path,80)
    assert report['status']==status and report['score']==score
    assert report['recommendations']


@pytest.mark.parametrize('kind',['timeout','failure','missing','malformed','exception','disabled'])
def test_measurement_problems_are_reported_without_changing_acceptance(tmp_path,monkeypatch,kind):
    import runtime.behavior_conversion.verification_test_strength as strength
    project, session, receipt, profile=setup_measurement(tmp_path,enabled=kind!='disabled')
    before=(project/'pom.xml').read_bytes()
    calls=[]
    def run(command,directory,timeout,environment):
        calls.append(command)
        if kind=='exception': raise OSError('PIT unavailable')
        if kind=='malformed':
            raw=session.strength_directory/'pit-reports/mutations.xml'; raw.parent.mkdir(); raw.write_text('<invalid>')
        return (1 if kind=='failure' else 0,'diagnostic',kind=='timeout')
    monkeypatch.setattr(strength,'run_mutations',run)
    report=measure_accepted_unit(session,profile,receipt)
    assert report['status']==('disabled' if kind=='disabled' else 'timed_out' if kind=='timeout' else 'tool_error')
    assert report['affects_acceptance'] is False and receipt['candidate_hash']=='accepted-revision'
    assert (project/'pom.xml').read_bytes()==before
    assert bool(calls)==(kind!='disabled')
    directory=Path(report['report_directory'])
    assert json.loads((directory/'test-strength.json').read_text())['status']==report['status']


def test_real_pit_reports_survivors_and_uncovered_branches(tmp_path):
    """Use real PIT/JUnit; weak assertions pass tests but must leave observable mutants alive."""
    from runtime.java_toolchain import resolve_java_home
    project,session,receipt,profile=setup_measurement(tmp_path)
    profile.java_home=resolve_java_home(25)
    session.mutation_settings.timeout_seconds=300
    before=(project/'pom.xml').read_bytes()
    report=measure_accepted_unit(session,profile,receipt)
    assert report['status']=='completed',report
    assert report['counts'].get('SURVIVED',0)>0 and report['score']<80
    assert report['recommendations'] and report['raw_report_hash']
    assert report['pit_version']==PIT_VERSION and report['affects_acceptance'] is False
    assert (project/'pom.xml').read_bytes()==before
    strong_root=tmp_path/'strong'; strong_root.mkdir()
    strong_project,strong_session,strong_receipt,strong_profile=setup_measurement(strong_root)
    strong_profile.java_home=profile.java_home
    test=strong_project/'src/test/java/example/BalanceTest.java'
    test.write_text('''package example; public class BalanceTest {
@org.junit.jupiter.api.Test public void values(){ Balance b=new Balance();
org.junit.jupiter.api.Assertions.assertEquals(4,b.available(3));
org.junit.jupiter.api.Assertions.assertEquals(0,b.available(0));
org.junit.jupiter.api.Assertions.assertEquals(0,b.available(-1)); } }''')
    # A new accepted attempt snapshots the stronger suite; no report is reused across revisions.
    strong_session.attempt=strong_root/'stronger-attempt'; strong_session.attempt.mkdir()
    prepare_measurement(strong_session,strong_project,candidate())
    strong=measure_accepted_unit(strong_session,strong_profile,strong_receipt)
    assert strong['status']=='completed',strong
    assert strong['score']>report['score'] and strong['counts'].get('SURVIVED',0)==0


def test_timeout_terminates_the_measurement_process(tmp_path):
    import sys
    from tools.behavior_verification.mutation_execution import run_mutations
    code, output, timed_out=run_mutations([sys.executable,'-c','import time; time.sleep(30)'],tmp_path,0.2,None)
    assert timed_out and code!=0
