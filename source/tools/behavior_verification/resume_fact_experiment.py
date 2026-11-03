"""Resume an isolated facts experiment with explicit, scoped composition upgrades."""
import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from runtime.configuration import load_configuration
from runtime.behavior_conversion.stage_tasks import StageTasks
from runtime.behavior_conversion.verification_mode import facts_disabled
from runtime.component_conversion.saved_experiment import retain_packages, candidate_key
from runtime.model_execution.error_details import SafeDiagnosticFormatter, sanitize_diagnostic
from tools.behavior_verification.experimental_checkpoint import copy_checkpoint, load_candidates, file_hash, refresh_preparation, verify_saved_inputs, preflight_saved_inputs
from tools.state_store_tools.db import get_connection


def run(source, profile_path, run_id, *, retry_preparation=False, continue_experiment=False, regenerate_formats=(), format_feedback=None, corrected_formats=(), retained_metadata=(), retained_tests=(), correction_attempts=None, automatic_chain_replay=False):
    """Revalidate saved Java, allowing only explicitly selected composition upgrades."""
    profile = load_configuration(profile_path)
    if not facts_disabled(profile):
        raise ValueError('Explicit facts-disabled experimental profile required')
    if profile.enable_git:
        raise ValueError('Experimental continuation must not enable Git publication')
    destination = Path(profile.output_root).resolve()
    regenerate_formats = set(regenerate_formats)
    if automatic_chain_replay and (not regenerate_formats or corrected_formats or retained_metadata or retained_tests or format_feedback):
        raise ValueError('Automatic chain replay requires selected formats and forbids manual Java, metadata, tests or repair feedback')
    configured_attempts = profile.max_agent_task_retries
    if correction_attempts is not None:
        if not regenerate_formats or correction_attempts < configured_attempts:
            raise ValueError('Run-only correction cap must increase the bound for explicitly selected compositions')
        profile.max_agent_task_retries = correction_attempts
    from models.native_implementation import NativeImplementation
    from tools.component_inventory_tools.identity import stable_id
    corrected = {}
    for value in corrected_formats:
        label,path = value.split('=',1)
        if label not in regenerate_formats or label in corrected:
            raise ValueError('Corrected Java must belong to a distinct selected format composition')
        corrected[label] = (NativeImplementation.model_validate_json(Path(path).read_text(encoding='utf-8')),str(Path(path).resolve()))
    metadata_files, test_files = {}, {}
    for values,selected in ((retained_metadata,metadata_files),(retained_tests,test_files)):
        for value in values:
            label,path = value.split('=',1)
            if label not in corrected or label in selected:
                raise ValueError('Retained metadata/tests require a distinct corrected selected composition')
            selected[label] = Path(path).resolve()
    if regenerate_formats and not continue_experiment:
        raise ValueError('Format upgrades require an existing experimental checkpoint')
    repair_feedback = json.loads(Path(format_feedback).read_text(encoding='utf-8')) if format_feedback else {}
    if not isinstance(repair_feedback,dict) or set(repair_feedback)-regenerate_formats or any(not isinstance(value,str) for value in repair_feedback.values()):
        raise ValueError('Repair feedback must describe only explicitly selected format compositions')
    if continue_experiment:
        report = json.loads((destination/'experimental-continuation.json').read_text(encoding='utf-8'))
        from tools.behavior_verification.component_pilot_run import process_alive
        if process_alive(report['pid']):
            raise ValueError('Experimental continuation is already running')
        if file_hash(report['original_database']) != report['original_database_hash']:
            raise ValueError('Original checkpoint changed')
        with (destination/'continuation-history.jsonl').open('a',encoding='utf-8') as history:
            history.write(json.dumps(report)+'\n')
        for key in ('phase','error','finished_at'):
            report.pop(key,None)
    elif retry_preparation:
        report = json.loads((destination/'experimental-continuation.json').read_text(encoding='utf-8'))
        if report.get('phase') != 'conversion_scoped_stale' or report.get('implementation_attempts_before') != report.get('implementation_attempts_after'):
            raise ValueError('Only a preparation-only stopped copy may be refreshed')
        if file_hash(report['original_database']) != report['original_database_hash']:
            raise ValueError('Original checkpoint changed')
        (destination/'first-preparation-attempt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        with get_connection(str(destination/run_id/'state/migration.db')) as copied:
            original = sqlite3.connect('file:'+Path(report['original_database']).as_posix()+'?mode=ro',uri=True)
            try:
                config = json.loads(original.execute('SELECT run_config_json FROM runs WHERE run_id=?',(run_id,)).fetchone()[0])
            finally:
                original.close()
            config['output_root'] = str(destination/Path(config['output_root']).resolve().relative_to(Path(source).resolve()))
            copied.execute('UPDATE runs SET run_config_json=? WHERE run_id=?',(json.dumps(config),run_id))
            refresh_preparation(copied,destination,run_id)
        for key in ('phase','error','finished_at'):
            report.pop(key,None)
    else:
        report = copy_checkpoint(source,destination,run_id,profile)
    report.update(status='preparing',pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        experimental_only=True,implementation_regeneration_for_saved_candidates=bool(regenerate_formats),counters_reset=False,groups={})
    report['authorized_format_regeneration'] = sorted(regenerate_formats)
    report['automatic_chain_replay'] = automatic_chain_replay
    report['full_conversion_resumed'] = False if regenerate_formats else None
    report['correction_attempt_cap'] = dict(configured=configured_attempts,effective=profile.max_agent_task_retries,
        scope=sorted(regenerate_formats),run_only=True,counters_reset=False)
    report['explicit_composition_corrections'] = {label:dict(path=path,java_hash=stable_id(value.model_dump(mode='json'))) for label,(value,path) in corrected.items()}
    report['retained_composition_evidence'] = {label:dict(metadata=str(metadata_files.get(label,'')),tests=str(test_files.get(label,'')),
        metadata_hash=file_hash(metadata_files[label]) if label in metadata_files else None,
        tests_hash=file_hash(test_files[label]) if label in test_files else None) for label in corrected}
    if format_feedback:
        report['composition_repair_feedback'] = dict(path=str(Path(format_feedback).resolve()),hash=file_hash(format_feedback))
    report_path = destination/'experimental-continuation.json'
    def save():
        temporary = report_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report,indent=2),encoding='utf-8')
        temporary.replace(report_path)
    save()
    (destination/'continuation-pid.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=report['started_at'],
        run_directory=run_id,log='experimental-continuation.log',final_report='experimental-continuation.json',
        experimental_only=True,credential_source='Windows user environment'),indent=2),encoding='utf-8')
    handlers = [logging.FileHandler(destination/'experimental-continuation.log',encoding='utf-8')]
    handlers[0].setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=handlers,force=True)
    conn = get_connection(str(destination/run_id/'state/migration.db'))
    original_init = StageTasks.__init__
    original_ask = StageTasks.ask
    stop = Event()
    from tools.behavior_verification.component_pilot import publish_component_run
    def observe():
        while not stop.wait(15):
            try:
                publish_component_run(destination,run_id,running=True)
            except Exception as error:
                logging.warning('Progress publication: %s',sanitize_diagnostic(str(error)))
    observer = Thread(target=observe,daemon=True)
    observer.start()
    try:
        saved = load_candidates(conn)
        from tools.behavior_verification.format_regeneration_scope import selected_composition, guarded_model_call, retained_java, composition_upgrade_requests, convert_selected_compositions
        baselines = {}
        for item in saved.values():
            if selected_composition(item[2],regenerate_formats):
                baselines.setdefault(item[2]['configured_format']['logical_id'],item[1])
        if set(baselines) != regenerate_formats:
            raise ValueError('Regeneration selection must match saved complete format compositions')
        preserved_java = retained_java(conn,run_id,regenerate_formats) if regenerate_formats else {}
        report['retained_java_hashes'] = preserved_java
        by_origin = {}
        for identity,item in saved.items():
            key = candidate_key(item[2]['components'])
            if key in by_origin and by_origin[key][1] != item[1] and not selected_composition(item[2],regenerate_formats):
                raise ValueError('Ambiguous saved implementation source/configuration')
            by_origin[key] = item
        report['saved_candidates'] = len(saved)
        from models.common_models import RunConfig
        config = RunConfig.model_validate_json(conn.execute('SELECT run_config_json FROM runs WHERE run_id=?',(run_id,)).fetchone()[0])
        report['source_configuration_preflight_passed'] = preflight_saved_inputs(conn,config,profile,saved)
        if automatic_chain_replay:
            marker=destination/'automatic-chain-replay-start.json'
            if not marker.exists():
                from tools.state_store_tools import component_records
                plan=json.loads(conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?',(run_id,)).fetchone()[0])
                targets=[group['group_id'] for group in plan['groups'] if any(plan['components'][member]['kind']=='format_composition' and plan['components'][member]['label'] in regenerate_formats for member in group['members'])]
                if len(targets)!=len(regenerate_formats):raise ValueError('Automatic replay targets are missing or ambiguous')
                backup=destination/'before-automatic-chain-replay.db'
                if backup.exists():raise ValueError('Automatic replay backup already exists without its audit record')
                with sqlite3.connect(backup) as archive:conn.backup(archive)
                heads={key:component_records.head(conn,run_id,key) for key in targets}
                component_records.invalidate(conn,run_id,targets);conn.commit()
                marker.write_text(json.dumps(dict(targets=targets,prior_heads=heads,backup=str(backup),manual_overrides_allowed=False,counters_reset=False),indent=2),encoding='utf-8')
        report['implementation_attempts_before'] = [list(row) for row in conn.execute("SELECT identity,revision,attempts FROM staged_conversion_tasks WHERE stage='implementation'")]
        def initialize(self,*args,**kwargs):
            original_init(self,*args,**kwargs)
            allowed = selected_composition(self.payload or {},regenerate_formats)
            if regenerate_formats:
                self.call = guarded_model_call(self.call,allowed)
            item = saved.get(self.identity) or by_origin.get(candidate_key(self.payload.get('components',{})))
            if item is None:
                labels = {node['label'] for node in self.payload.get('components',{}).values()}
                if any(labels.intersection(node['label'] for node in prior['components'].values()) for _,_,prior in saved.values()):
                    raise ValueError('Saved candidate configuration changed; refusing regeneration: '+self.identity)
                return
            value,digest,prior = item
            verify_saved_inputs(prior,self.payload)
            if allowed:
                report['groups'][self.identity] = dict(status='composition_regeneration_enabled',previous_java_hash=digest,
                    new_task_revision=self.revision,retained_attempt_history=True)
                label = self.payload['configured_format']['logical_id']
                if label in corrected:
                    replacement,path = corrected[label]
                    self.validator.frozen_implementation = replacement.model_copy(deep=True)
                    self.validator.frozen_implementation_hash = stable_id(replacement.model_dump(mode='json'))
                    report['groups'][self.identity].update(status='corrected_composition_revalidation',corrected_java=path)
                    if label in test_files:
                        from models.native_test_bundle import NativeTestBundle
                        self.validator.frozen_tests = NativeTestBundle.model_validate_json(test_files[label].read_text(encoding='utf-8'))
                save()
                return
            self.validator.frozen_implementation = value.model_copy(deep=True)
            self.validator.frozen_implementation_hash = digest
            report['groups'][self.identity] = dict(status='fresh_validation_started',java_hash=digest)
            save()
        StageTasks.__init__ = initialize
        def ask(self,stage,request,prompt,schema,check,**kwargs):
            label = (self.payload.get('configured_format') or {}).get('logical_id')
            if stage=='semantic_metadata' and label in metadata_files:
                self.fresh()
                value = schema.model_validate_json(metadata_files[label].read_text(encoding='utf-8'))
                check(value)
                from tools.state_store_tools import staged_conversion_state as state_store
                state_store.retain(self.conn,self.config.run_id,self.identity,self.revision,stage,value.model_dump(mode='json'),stable_id(value.model_dump(mode='json')))
                return value
            return original_ask(self,stage,request,prompt,schema,check,**kwargs)
        StageTasks.ask = ask
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:
            credential = winreg.QueryValueEx(environment,profile.model_api_key_environment)[0]
        if not isinstance(credential,str) or not credential.strip():
            raise ValueError('Windows user API credential is missing')
        os.environ[profile.model_api_key_environment] = credential
        del credential
        report.update(status='running',credential_source='Windows user environment')
        save()
        from runtime.checkpoints import resume_pipeline
        packages = {key:item[2]['native_package'] for key,item in saved.items()}
        packages.update({key:item[2]['native_package'] for key,item in by_origin.items()})
        with retain_packages(packages), composition_upgrade_requests(regenerate_formats,baselines,repair_feedback,automatic=automatic_chain_replay):
            if regenerate_formats:
                report['selected_format_outcomes'] = convert_selected_compositions(conn,config,profile,destination/run_id,regenerate_formats,report.get('outcome',{}))
            else:
                resume_pipeline(str(destination),run_id)
        state = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?',(run_id,)).fetchone()
        report.update(status=state[0],phase=state[1])
    except Exception as error:
        report.update(status='blocked',error=sanitize_diagnostic(str(error)))
        logging.exception('Experimental continuation stopped')
    finally:
        stop.set()
        observer.join(timeout=10)
        StageTasks.__init__ = original_init
        StageTasks.ask = original_ask
        report['implementation_attempts_after'] = [list(row) for row in conn.execute("SELECT identity,revision,attempts FROM staged_conversion_tasks WHERE stage='implementation'")]
        report['original_database_unchanged'] = file_hash(report['original_database']) == report['original_database_hash']
        if report.get('retained_java_hashes'):
            report['retained_java_unchanged'] = all(file_hash(path)==digest for path,digest in report['retained_java_hashes'].items())
        if automatic_chain_replay:
            from tools.behavior_verification.format_regeneration_scope import automatic_java_provenance
            report['automatic_java_provenance']=automatic_java_provenance(conn,run_id,report['groups'])
        try:
            report['outcome'] = publish_component_run(destination,run_id,running=False,error=report.get('error'))
        except Exception as error:
            report['progress_report_error'] = sanitize_diagnostic(str(error))
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()
        conn.close()
        logging.shutdown()
    return 0 if report['status']=='completed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--run-id',default='single-get-client-links')
    parser.add_argument('--retry-preparation',action='store_true')
    parser.add_argument('--continue-experiment',action='store_true')
    parser.add_argument('--regenerate-format',action='append',default=[],help='Explicit saved format-composition label allowed to generate replacement Java')
    parser.add_argument('--format-feedback',help='JSON object containing source-backed focused repair feedback for selected format labels')
    parser.add_argument('--corrected-format',action='append',default=[],help='LABEL=JSON: explicitly corrected selected composition, frozen for canonical revalidation')
    parser.add_argument('--retained-format-metadata',action='append',default=[],help='LABEL=JSON: saved model metadata to recheck canonically without another model call')
    parser.add_argument('--retained-format-tests',action='append',default=[],help='LABEL=JSON: saved source-backed tests to rerun without changing expectations')
    parser.add_argument('--correction-attempts',type=int,help='Run-only per-stage cap for explicitly selected composition upgrades; used attempts remain counted')
    parser.add_argument('--automatic-chain-replay',action='store_true',help='Fresh selected format generation; forbid all manual candidate/metadata/test overrides')
    args = parser.parse_args()
    raise SystemExit(run(args.source,args.profile,args.run_id,retry_preparation=args.retry_preparation,continue_experiment=args.continue_experiment,regenerate_formats=args.regenerate_format,format_feedback=args.format_feedback,corrected_formats=args.corrected_format,retained_metadata=args.retained_format_metadata,retained_tests=args.retained_format_tests,correction_attempts=args.correction_attempts,automatic_chain_replay=args.automatic_chain_replay))
