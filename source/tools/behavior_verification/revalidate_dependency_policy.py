"""Fork a stopped checkpoint and revalidate every saved component under one shared lock."""
import argparse
import json
import logging
import os
from datetime import datetime,timezone
from pathlib import Path
from threading import Event,Thread
from models.common_models import RunConfig
from runtime.configuration import load_configuration
from runtime.component_conversion.saved_experiment import candidate_key,retain_packages
from runtime.dependency_policy import load_policy
from runtime.behavior_conversion.verification_mode import facts_disabled
from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
from tools.behavior_verification.experimental_checkpoint import copy_checkpoint,load_candidates,file_hash,preflight_saved_inputs
from tools.behavior_verification.format_regeneration_scope import retained_java,convert_selected_compositions
from tools.behavior_verification.frozen_dependency_replay import frozen_dependency_replay
from tools.behavior_verification.component_pilot import publish_component_run
from tools.behavior_verification.component_pilot_run import process_alive
from tools.state_store_tools.db import get_connection
from tools.state_store_tools import dependency_locks
from tools.component_inventory_tools.identity import stable_id
from tools.conversion_tools.scoped_reuse.fingerprints import digest as policy_digest


def run(source,profile_path,run_id):
    """Preserve the source checkpoint; publish only new dependency-aligned component receipts."""
    profile=load_configuration(profile_path);policy=load_policy(profile)
    if not policy or not facts_disabled(profile) or profile.enable_git or profile.format_comparison.max_cases!=64:
        raise ValueError('Require the existing experimental checks, no publication, shared policy and 64-case bound')
    source=Path(source).resolve();directory=Path(profile.output_root).resolve()
    for name in ('experimental-continuation.json','format-tests-policy-revalidation.json','dependency-policy-revalidation.json'):
        path=source/name
        if path.exists() and process_alive(json.loads(path.read_text())['pid']):raise ValueError('Source checkpoint still has an active continuation')
    path=directory/'dependency-policy-revalidation.json'
    if directory.exists():
        report=json.loads(path.read_text(encoding='utf-8'))
        if process_alive(report['pid']):raise ValueError('Dependency revalidation is already running')
        if report['policy_hash']!=policy_digest(policy.model_dump(mode='json')):raise ValueError('Use a new checkpoint for another dependency policy revision')
        with (directory/'dependency-policy-history.jsonl').open('a',encoding='utf-8') as history:history.write(json.dumps(report)+'\n')
    else:report=copy_checkpoint(source,directory,run_id,profile)
    if file_hash(report['original_database'])!=report['original_database_hash']:raise ValueError('Original checkpoint changed')
    report.update(status='preparing',pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        policy_hash=policy_digest(policy.model_dump(mode='json')),policy=policy.model_dump(mode='json'),full_conversion_resumed=False,
        implementation_regeneration_allowed=False,counters_reset=False,groups={})
    def save():
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(path)
    save();handler=logging.FileHandler(directory/'dependency-policy-revalidation.log',encoding='utf-8')
    handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler],force=True)
    conn=get_connection(str(directory/run_id/'state/migration.db'));stop=Event()
    def observe():
        while not stop.wait(15):
            try:publish_component_run(directory,run_id,running=True)
            except Exception as error:logging.warning('Progress publication: %s',sanitize_diagnostic(str(error)))
    observer=Thread(target=observe,daemon=True)
    try:
        saved=load_candidates(conn);by_origin={candidate_key(item[2]['components']):item for item in saved.values()}
        report['saved_components']=len(by_origin)
        report.setdefault('saved_java_hashes',{}).update(retained_java(conn,run_id,set()))
        config=RunConfig.model_validate_json(conn.execute('SELECT run_config_json FROM runs WHERE run_id=?',(run_id,)).fetchone()[0])
        report['source_configuration_preflight_passed']=preflight_saved_inputs(conn,config,profile,saved)
        report['attempts_before']=[list(row) for row in conn.execute('SELECT identity,revision,stage,attempts FROM staged_conversion_tasks')]
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:
            credential=winreg.QueryValueEx(environment,profile.model_api_key_environment)[0]
        if not isinstance(credential,str) or not credential.strip():raise ValueError('Windows user API credential missing')
        os.environ[profile.model_api_key_environment]=credential;del credential
        report.update(status='running',credential_source='Windows user environment');save()
        (directory/'continuation-pid.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=report['started_at'],
            log='dependency-policy-revalidation.log',final_report=path.name,full_conversion_resumed=False),indent=2),encoding='utf-8')
        observer.start();packages={key:item[2]['native_package'] for key,item in saved.items()}
        packages.update({key:item[2]['native_package'] for key,item in by_origin.items()})
        with retain_packages(packages),frozen_dependency_replay(conn,by_origin,report,save):
            report['component_outcomes']=convert_selected_compositions(conn,config,profile,directory/run_id,set(),{},saved_components=by_origin)
        report['status']='completed' if all(item['status']=='component_validated' for item in report['component_outcomes'].values()) else 'blocked'
    except Exception as error:
        report.update(status='blocked',error=sanitize_diagnostic(str(error)));logging.exception('Dependency revalidation stopped')
    finally:
        stop.set()
        if observer.is_alive():observer.join(timeout=10)
        report['original_database_unchanged']=file_hash(report['original_database'])==report['original_database_hash']
        report['saved_java_unchanged']=all(file_hash(path)==digest for path,digest in report.get('saved_java_hashes',{}).items())
        report['implementation_model_calls']=sum(conn.execute("SELECT count(*) FROM staged_conversion_attempts WHERE identity=? AND revision=? AND stage='implementation'",(key,item['revision'])).fetchone()[0] for key,item in report['groups'].items())
        report['dependency_lock']=dependency_locks.read(conn,run_id,policy_digest(policy.model_dump(mode='json')))
        report['attempts_after']=[list(row) for row in conn.execute('SELECT identity,revision,stage,attempts FROM staged_conversion_tasks')]
        try:report['outcome']=publish_component_run(directory,run_id,running=False,error=report.get('error'))
        except Exception as error:report['progress_report_error']=sanitize_diagnostic(str(error))
        report['finished_at']=datetime.now(timezone.utc).isoformat();save();conn.commit();conn.close();logging.shutdown()
    return 0 if report['status']=='completed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True);parser.add_argument('--profile',required=True);parser.add_argument('--run-id',default='single-get-client-links')
    args=parser.parse_args();raise SystemExit(run(args.source,args.profile,args.run_id))
