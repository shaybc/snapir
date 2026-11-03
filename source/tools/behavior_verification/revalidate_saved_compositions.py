"""Revalidate selected frozen format compositions under the tests-based composition policy."""
import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from threading import Event,Thread
from models.common_models import RunConfig
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from runtime.behavior_conversion.stage_tasks import StageTasks
from runtime.behavior_conversion.verification_mode import facts_disabled
from runtime.component_conversion.saved_experiment import candidate_key,retain_packages
from runtime.configuration import load_configuration
from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
from tools.behavior_verification.component_pilot import publish_component_run
from tools.behavior_verification.component_pilot_run import process_alive
from tools.behavior_verification.experimental_checkpoint import load_candidates,file_hash,preflight_saved_inputs,verify_saved_inputs
from tools.behavior_verification.format_regeneration_scope import retained_java,guarded_model_call,convert_selected_compositions,selected_composition
from tools.component_inventory_tools.identity import stable_id
from tools.conversion_tools.component_identity import FORMAT_COMPOSITION_POLICY_VERSION
from tools.state_store_tools.db import get_connection


def retained_tests(conn,identity,digest):
    """Reuse passing tests only when their stage belongs to this exact production candidate."""
    rows=conn.execute("SELECT t.artifact_json,i.artifact_json FROM staged_conversion_tasks t JOIN staged_conversion_tasks i ON i.run_id=t.run_id AND i.identity=t.identity AND i.revision=t.revision AND i.stage='implementation' WHERE t.identity=? AND t.stage='tests' AND t.status='retained' ORDER BY t.updated_at DESC",(identity,))
    for tests,production in rows:
        if production and stable_id(NativeImplementation.model_validate_json(production).model_dump(mode='json'))==digest:
            return NativeTestBundle.model_validate_json(tests)
    return None


def run(profile_path,labels,run_id='single-get-client-links'):
    """Use canonical component validation; refuse every implementation model request or repair."""
    profile=load_configuration(profile_path)
    if not facts_disabled(profile) or profile.enable_git:
        raise ValueError('This saved-candidate trial requires the existing facts-disabled, publication-disabled profile')
    directory=Path(profile.output_root).resolve();labels=set(labels)
    baseline=json.loads((directory/'experimental-continuation.json').read_text(encoding='utf-8'))
    if process_alive(baseline['pid']):raise ValueError('Another experimental continuation is running')
    report_path=directory/'format-tests-policy-revalidation.json'
    if report_path.exists():
        previous=json.loads(report_path.read_text(encoding='utf-8'))
        if process_alive(previous['pid']):raise ValueError('Composition revalidation is already running')
        with (directory/'format-tests-policy-history.jsonl').open('a',encoding='utf-8') as history:history.write(json.dumps(previous)+'\n')
    if file_hash(baseline['original_database'])!=baseline['original_database_hash']:
        raise ValueError('Original conversion database changed')
    report=dict(status='preparing',pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        policy=FORMAT_COMPOSITION_POLICY_VERSION,formats=sorted(labels),full_conversion_resumed=False,
        implementation_regeneration_allowed=False,counters_reset=False,groups={},
        attempt_allowance=dict(per_stage=profile.max_agent_task_retries,basis='Fresh versioned composition policy; historical tasks and attempts retained'))
    def save():
        temporary=report_path.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(report_path)
    save()
    handler=logging.FileHandler(directory/'format-tests-policy-revalidation.log',encoding='utf-8')
    handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler],force=True)
    conn=get_connection(str(directory/run_id/'state/migration.db'));original_init=StageTasks.__init__
    stop=Event()
    def observe():
        while not stop.wait(15):
            try:publish_component_run(directory,run_id,running=True)
            except Exception as error:logging.warning('Progress publication: %s',sanitize_diagnostic(str(error)))
    observer=Thread(target=observe,daemon=True)
    try:
        backup=directory/('before-'+FORMAT_COMPOSITION_POLICY_VERSION+'.db')
        if not backup.exists():
            with sqlite3.connect(backup) as archive:conn.backup(archive)
        saved=load_candidates(conn)
        by_origin={candidate_key(item[2]['components']):item for item in saved.values()}
        selected={item[2]['configured_format']['logical_id']:item for item in by_origin.values() if selected_composition(item[2],labels)}
        if set(selected)!=labels:raise ValueError('Every selected composition must have verified saved Java')
        config=RunConfig.model_validate_json(conn.execute('SELECT run_config_json FROM runs WHERE run_id=?',(run_id,)).fetchone()[0])
        report['source_configuration_preflight_passed']=preflight_saved_inputs(conn,config,profile,saved)
        report['retained_java_hashes']=retained_java(conn,run_id,labels)
        report['frozen_production_hashes']={label:item[1] for label,item in selected.items()}
        report['attempts_before']=[list(row) for row in conn.execute('SELECT identity,revision,stage,attempts FROM staged_conversion_tasks')]
        def initialize(self,*args,**kwargs):
            original_init(self,*args,**kwargs)
            self.call=guarded_model_call(self.call,False)
            item=by_origin.get(candidate_key((self.payload or {}).get('components',{})))
            if item is None:raise ValueError('No verified saved candidate for '+self.identity)
            production,digest,prior=item;verify_saved_inputs(prior,self.payload)
            self.validator.frozen_implementation=production.model_copy(deep=True)
            self.validator.frozen_implementation_hash=digest
            if selected_composition(self.payload,labels):
                tests=retained_tests(conn,self.identity,digest)
                if tests is not None:self.validator.frozen_tests=tests
                report['groups'][self.identity]=dict(label=self.payload['configured_format']['logical_id'],revision=self.revision,
                    java_hash=digest,retained_tests=tests is not None)
                save()
        StageTasks.__init__=initialize
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:
            credential=winreg.QueryValueEx(environment,profile.model_api_key_environment)[0]
        if not isinstance(credential,str) or not credential.strip():raise ValueError('Windows user API credential is missing')
        os.environ[profile.model_api_key_environment]=credential;del credential
        report.update(status='running',credential_source='Windows user environment');save()
        (directory/'continuation-pid.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=report['started_at'],
            log='format-tests-policy-revalidation.log',final_report=report_path.name,full_conversion_resumed=False),indent=2),encoding='utf-8')
        observer.start()
        packages={key:item[2]['native_package'] for key,item in saved.items()}
        packages.update({key:item[2]['native_package'] for key,item in by_origin.items()})
        with retain_packages(packages):
            report['selected_format_outcomes']=convert_selected_compositions(conn,config,profile,directory/run_id,labels,baseline.get('outcome',{}))
        report['status']='completed' if all(value['status']=='component_validated' for value in report['selected_format_outcomes'].values()) else 'blocked'
    except Exception as error:
        report.update(status='blocked',error=sanitize_diagnostic(str(error)));logging.exception('Frozen composition revalidation stopped')
    finally:
        stop.set()
        if observer.is_alive():observer.join(timeout=10)
        StageTasks.__init__=original_init
        report['attempts_after']=[list(row) for row in conn.execute('SELECT identity,revision,stage,attempts FROM staged_conversion_tasks')]
        report['original_database_unchanged']=file_hash(baseline['original_database'])==baseline['original_database_hash']
        report['retained_java_unchanged']=all(file_hash(path)==digest for path,digest in report.get('retained_java_hashes',{}).items())
        report['implementation_model_calls']=sum(conn.execute("SELECT count(*) FROM staged_conversion_attempts WHERE identity=? AND revision=? AND stage='implementation'",(key,item['revision'])).fetchone()[0] for key,item in report['groups'].items())
        try:report['outcome']=publish_component_run(directory,run_id,running=False,error=report.get('error'))
        except Exception as error:report['progress_report_error']=sanitize_diagnostic(str(error))
        report['finished_at']=datetime.now(timezone.utc).isoformat();save();conn.close();logging.shutdown()
    return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--format',action='append',required=True)
    parser.add_argument('--run-id',default='single-get-client-links')
    args=parser.parse_args()
    raise SystemExit(run(args.profile,args.format,args.run_id))
