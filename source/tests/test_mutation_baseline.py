"""Baseline reuse requires exact provenance; stale evidence always falls back to fresh execution."""
import hashlib
import json
import os
from pathlib import Path
import pytest
from models.boundary_case import BoundaryCase
from models.boundary_comparison_report import BoundaryComparisonReport
from models.boundary_harness_binding import BoundaryHarnessBinding
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.independent_comparison import VERSION
from tools.behavior_verification.mutation_baseline import reusable_baseline
from test_behavior_verification_boundaries import unit,source


def saved(tmp_path,monkeypatch):
    monkeypatch.setattr('tools.behavior_verification.mutation_baseline.runtime_fingerprint',lambda:'runtime')
    original=unit(sources=[source('work','package example; public class Work { public int execute(){return 7;} }')])
    boundary=boundary_contract(original)
    native=BoundaryHarnessBinding(adapter_class='fixture.Adapter',sources=[dict(path='fixture/Adapter.java',content='native source')])
    legacy=BoundaryHarnessBinding(adapter_class='legacy.Adapter')
    tool=tmp_path/'tool.jar';tool.write_bytes(b'analysis tool')
    dependency=tmp_path/'dependency.jar';dependency.write_bytes(b'dependency')
    native.classpath=[str(dependency)]
    case=BoundaryCase(case_id='first')
    digest=lambda b:hashlib.sha256(b).hexdigest()
    hashes={}
    for side,binding in [('legacy',legacy),('native',native)]:
        hashes[side+':tool']=digest(tool.read_bytes())
        hashes[side+':binding']=digest(json.dumps(binding.model_dump(mode='json'),sort_keys=True).encode())
    hashes['native:dependency:'+str(dependency)]=digest(dependency.read_bytes())
    hashes.update({'legacy:source:work':original['sources'][0]['content_hash'],'legacy:compiled_text:work':digest(original['sources'][0]['content'].encode()),
        'native:source:fixture/Adapter.java':digest(b'native source'),'native:compiled_text:fixture/Adapter.java':digest(b'native source')})
    observation=dict(case_id='first',status='completed',invocation_completed=True)
    report=BoundaryComparisonReport(unit_id=boundary.unit_id,status='matched_observed_cases',
        source_manifest_hash=boundary.source_manifest_hash,configuration_hash=boundary.configuration_hash,artifact_hashes=hashes,
        execution_environment=dict(runtime_fingerprint='runtime',comparison_policy=VERSION,java_version='25',case_timeout_seconds=15,
            assertions_enabled=True,timezone='UTC',locale='ROOT',isolation='fresh_JVM_per_side_per_case'),
        cases=[dict(case=case.model_dump(mode='json'),legacy=observation,native=observation,comparison_status='matched',limitations=[],differences=[])])
    path=tmp_path/'baseline.json';path.write_text(report.model_dump_json(),encoding='utf-8')
    job=dict(unit=original,java_version=25,candidate_sources={'fixture/Adapter.java':digest(b'native source')},
        verified_baseline=dict(path=str(path),sha256=digest(path.read_bytes())))
    return job,boundary,legacy,native,[case],tool


def test_exact_baseline_can_be_reused(tmp_path,monkeypatch):
    args=saved(tmp_path,monkeypatch)
    report,reason=reusable_baseline(*args)
    assert report.status=='matched_observed_cases' and reason=='exact_verified_baseline'


@pytest.mark.parametrize('change',['report','input','configuration','source','native','binding','tool','dependency','environment','candidate_manifest','missing_reference'])
def test_changes_refuse_reuse(tmp_path,monkeypatch,change):
    args=saved(tmp_path,monkeypatch);job,boundary,legacy,native,cases,tool=args
    if change=='report':Path(job['verified_baseline']['path']).write_text('{}')
    elif change=='input':cases[0].input_xml='changed'
    elif change=='configuration':job['unit']['effective_configuration']['attributes']['extra']='changed'
    elif change=='source':job['unit']['sources'][0]['content']+=' changed'
    elif change=='native':native.sources[0].content+=' changed'
    elif change=='binding':native.adapter_class='changed.Adapter'
    elif change=='tool':tool.write_bytes(b'changed')
    elif change=='dependency':Path(native.classpath[0]).write_bytes(b'changed')
    elif change=='environment':monkeypatch.setattr('tools.behavior_verification.mutation_baseline.runtime_fingerprint',lambda:'different runtime')
    elif change=='candidate_manifest':job['candidate_sources']['fixture/Adapter.java']='changed'
    else:job.pop('verified_baseline')
    report,reason=reusable_baseline(*args)
    assert report is None and reason!='exact_verified_baseline'


def test_legacy_report_without_environment_fingerprint_is_not_reused(tmp_path,monkeypatch):
    args=saved(tmp_path,monkeypatch);reference=args[0]['verified_baseline'];path=Path(reference['path'])
    value=json.loads(path.read_text());value['execution_environment'].pop('runtime_fingerprint')
    path.write_text(json.dumps(value));reference['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    assert reusable_baseline(*args)[0] is None


def test_runtime_fingerprint_tracks_binaries_flags_cwd_and_policy_code(tmp_path,monkeypatch):
    from tools.behavior_verification import comparison_environment as module
    home=tmp_path/'jdk';(home/'bin').mkdir(parents=True)
    suffix='.exe' if os.name=='nt' else ''
    for name in ('java','javac'):(home/'bin'/(name+suffix)).write_bytes(name.encode())
    (home/'release').write_text('JDK fixture')
    environment={'JAVA_HOME':str(home)}
    monkeypatch.setattr(module,'java_environment',lambda:environment)
    fake=tmp_path/'source/tools/behavior_verification';fake.mkdir(parents=True)
    policy=fake/'policy.py';policy.write_text('policy one')
    monkeypatch.setattr(module,'__file__',str(fake/'comparison_environment.py'))
    first=module.runtime_fingerprint();assert module.runtime_fingerprint()==first
    environment['JAVA_TOOL_OPTIONS']='changed options';second=module.runtime_fingerprint();assert second!=first
    policy.write_text('policy two');third=module.runtime_fingerprint();assert third!=second
    (home/'bin'/('java'+suffix)).write_bytes(b'changed binary');fourth=module.runtime_fingerprint();assert fourth!=third
    monkeypatch.chdir(tmp_path);assert module.runtime_fingerprint()!=fourth
