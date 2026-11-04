"""Exercise AI fixture preparation on saved Java without opening conversion state for writes."""
import argparse
import json
import logging
import os
import shutil
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.native_unit_bundle import NativeSourceFile,NativeUnitBundle
from runtime.configuration import load_configuration
from runtime.behavior_conversion.stage_tasks import StageTasks
from runtime.behavior_conversion.native_metadata import inspect_native,resolve_dependencies
from runtime.behavior_conversion.bundle_output import accept_bundle,validate_bundle
from runtime.behavior_conversion.staged_pipeline import TESTS_ONLY
from runtime.behavior_conversion.testing_contract import testing_contract,validate_testing_contract
from runtime.component_conversion.format_chain_tests import validate_chain_tests
from runtime.java_toolchain import java_scope
from runtime.managed_projects import create_build_context
from runtime.dependency_policy import canonical_dependencies
from runtime.test_assets.preparation import prepare,asset_scope
from runtime.test_assets.junit_support import install_runtime,dependency,check_definition
from runtime.test_assets.materialization import comparison_plan
from runtime.format_comparison.runner import run_comparison
from runtime.step_comparison.runner import run_step_comparison
from agents.behavior_conversion.test_scenarios import TESTS
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.behavior_verification.experimental_checkpoint import file_hash
from tools.behavior_verification.boundary_contracts import boundary_contract


def run(profile_path,artifact_root,unit_path,output,*,resume=False):
    """Create an isolated test DB and retain all model attempts; never generate production Java."""
    profile=load_configuration(profile_path).model_copy(deep=True)
    profile.test_preparation.mode='ai_shared_fixtures_v1'
    root=Path(artifact_root).resolve();directory=Path(output).resolve()
    if directory==root or root in directory.parents or directory.exists() and not resume:raise ValueError('Pilot output must be new and separate from saved Java')
    if profile.format_comparison.max_cases!=64:raise ValueError('Pilot retains the existing 64-case limit')
    directory.mkdir(parents=True,exist_ok=True)
    previous=None
    if resume:
        from tools.behavior_verification.component_pilot_run import process_alive
        previous=json.loads((directory/'pilot.json').read_text(encoding='utf-8'))
        if process_alive(previous['pid']):raise ValueError('The isolated pilot is still active')
        with (directory/'pilot-history.jsonl').open('a',encoding='utf-8') as history:history.write(json.dumps(previous)+'\n')
    from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
    handler=logging.FileHandler(directory/'pilot.log',encoding='utf-8')
    handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler],force=True)
    report=dict(status='running',pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        full_conversion_resumed=False,production_generation_allowed=False,case_limit=64)
    def save():
        temp=directory/'pilot.tmp';temp.write_text(json.dumps(report,indent=2),encoding='utf-8');temp.replace(directory/'pilot.json')
    save();conn=get_connection(str(directory/'test-preparation.db'));create_all_tables(conn)
    config=SimpleNamespace(run_id='shared-fixture-pilot',output_root=str(directory))
    upsert_run(conn,run_id=config.run_id,run_mode='single_channel')
    paths=sorted((root/'src/main/java').rglob('*.java'));before={str(p):file_hash(p) for p in paths}
    if previous and previous['saved_java_hashes']!=before:raise ValueError('Saved pilot Java changed before resume')
    report['saved_java_hashes']=before
    unit=json.loads(Path(unit_path).read_text(encoding='utf-8'));unit_hash=digest(unit)
    records=list(root.glob('component-*.json'))
    if len(records)!=1:raise ValueError('Pilot needs one accepted component report')
    accepted=json.loads(records[0].read_text(encoding='utf-8'))
    for path in paths:
        relative=path.relative_to(root).as_posix()
        if accepted['files'].get(relative)!=file_hash(path):raise ValueError('Accepted native Java integrity failed')
    def fresh():
        if any(file_hash(p)!=h for p,h in before.items()) or digest(json.loads(Path(unit_path).read_text(encoding='utf-8')))!=unit_hash:
            raise ValueError('Saved pilot source/configuration changed')
    files=[NativeSourceFile(path=p.relative_to(root).as_posix(),content=p.read_bytes().decode('utf-8')) for p in paths]
    owned=set(accepted['owned_sources']);production=NativeImplementation(files=[f for f in files if f.path in owned])
    prerequisites={f.path:f.content for f in files if f.path not in owned}
    payload=dict(kind=unit['kind'],sources=unit['sources'],unit=unit,requirements={},format_chains=accepted.get('format_chains',[]))
    report['source_boundary']=boundary_contract(unit).model_dump(mode='json')
    validator=SimpleNamespace(fresh=fresh)
    revision=digest(dict(unit=unit_hash,java=before,policy=profile.test_preparation.model_dump(mode='json')))
    tasks=StageTasks(conn,config,profile,'saved-component',revision,None,validator)
    if resume:
        from tools.state_store_tools import staged_conversion_state as state
        for row in conn.execute("SELECT identity,revision,stage,attempts FROM staged_conversion_tasks WHERE status='running'").fetchall():
            state.finish(conn,config.run_id,row[0],row[1],row[2],row[3],error='Previous isolated pilot interrupted; attempt counter retained')
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:credential=winreg.QueryValueEx(environment,profile.model_api_key_environment)[0]
        if not isinstance(credential,str) or not credential.strip():raise ValueError('Windows user API credential missing')
        os.environ[profile.model_api_key_environment]=credential;del credential
        with java_scope(profile):
            inventory=inspect_native(files)
            assets=prepare(tasks,payload,production,inventory,prerequisites.items())
            report.update(asset_root=assets['root'],fixture_manifest_hash=assets['manifest_hash'],junit_scenarios=len(assets['junit'].scenarios),comparison_scenarios=len(assets['comparisons'].scenarios));save()
            if assets['bank'].unresolved or assets['junit'].unresolved or any(s.unresolved for s in assets['junit'].scenarios):
                raise ValueError('JUnit preparation has unresolved inputs; test-code generation was not invoked')
            install_runtime(profile)
            dependencies=canonical_dependencies(profile,accepted['dependencies'])
            known=[d.model_dump(mode='json') for d in [*dependencies,dependency()]]
            request=dict(production_files=[f.model_dump(mode='json') for f in files],parsed_apis=inventory,
                original_evidence=payload,requirements={},known_dependencies=known,
                shared_fixture_root='src/test/resources/shared-test-assets/'+assets['manifest_hash'],
                shared_fixture_manifest_hash=assets['manifest_hash'],fixture_bank=assets['bank'].model_dump(mode='json'),
                junit_scenarios=assets['junit'].model_dump(mode='json'),testing_contract=testing_contract(profile))
            def check(tests):
                fresh();check_definition(tests,assets);validate_chain_tests(tests,payload)
                metadata=inspect_native(tests.files)
                pins,missing=resolve_dependencies(metadata,known)
                if missing:raise ValueError('Undeclared test APIs: '+str(missing))
                bundle=NativeUnitBundle(files=[*production.files,*tests.files],dependencies=[*dependencies,*pins])
                validate_testing_contract(bundle,request['testing_contract'])
                values=validate_bundle(bundle)
                with asset_scope(dict(assets,tests=tests)):
                    validation,_=accept_bundle(directory/'junit',values,create_build_context,profile,[*dependencies,*pins],
                        dependency_files=prerequisites.items(),required_tests=[f.path for f in tests.files],testing_contract=request['testing_contract'],
                        pre_publish=lambda staged,context,validation:shutil.copytree(staged/'target',directory/'junit/target',dirs_exist_ok=True))
                report['junit_validation']=validation;save()
            tasks.ask('tests',request,TESTS_ONLY+'\n'+TESTS,NativeTestBundle,check)
            plan=comparison_plan(unit.get('logical_id','saved-component'),unit,files,assets['bank'],assets['comparisons'],assets['manifest_hash'])
            context=create_build_context(profile,directory/'junit','junit')
            from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
            plan.native_classpath=native_runtime_classpath(directory/'junit',context)
            plan.original_framework.classpath=list(profile.classpath_jars)
            execute=run_step_comparison if unit['kind']=='configured_step' else run_comparison
            report['comparison']=execute(plan,profile,directory/'comparison')
            report['status']='completed'
    except Exception as error:
        report.update(status='blocked',error=sanitize_diagnostic(str(error)));logging.exception('Shared fixture pilot stopped')
    finally:
        report['saved_java_unchanged']=all(file_hash(p)==h for p,h in before.items())
        report['attempts']=[list(row) for row in conn.execute('SELECT stage,attempts,status FROM staged_conversion_tasks')]
        report['finished_at']=datetime.now(timezone.utc).isoformat();save();conn.close();logging.shutdown()
    return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['profile','artifact-root','unit','output']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();raise SystemExit(run(args.profile,args.artifact_root,args.unit,args.output,resume=args.resume))
