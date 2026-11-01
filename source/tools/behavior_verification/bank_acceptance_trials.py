"""Run guarded bank-boundary trials before a fresh full-operation conversion; never change defaults."""
import argparse
import json
import logging
import os
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import yaml
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeUnitBundle
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.java_toolchain import java_scope
from runtime.model_execution.readiness import require_model_readiness
from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession,verification_session
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.verification_state import record_verification
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.thin_path_request import OPERATION,SELECTION,build_request
from tools.behavior_verification.bank_trial_inputs import load_trial_inputs
from tools.behavior_verification.acceptance_trial_validation import AcceptanceTrialValidator
from tools.behavior_verification.acceptance_trial_gates import boundaries_passed,rollout_ready


def publish(directory,report):
    """Retain real outcomes atomically, without claiming full operation acceptance early."""
    report['recorded_at']=datetime.now(timezone.utc).isoformat()
    report['accepted_boundaries']=sum(item.get('status')=='accepted' for item in report['units'].values())
    report['failed_boundaries']=sum(item.get('status')=='failed' for item in report['units'].values())
    report['incomplete_boundaries']=sum(item.get('status')=='verification_incomplete' for item in report['units'].values())
    report['pending_boundaries']=[name for _,name in SELECTION if name not in report['units']]
    path=directory/'acceptance-trials.json.tmp'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8');path.replace(directory/'acceptance-trials.json')


def run(input_run,output,*,model_name=None,prior_trials=None):
    """Keep historical evidence read-only and use normal staged roles and technical validators."""
    repository=Path(__file__).resolve().parents[3];input_run=Path(input_run).resolve();output=Path(output).resolve()
    if not output.is_relative_to(repository/'outputs') or output.exists():raise ValueError('Trials require a fresh repository outputs directory')
    profile=PipelineConfiguration.model_validate_json((input_run/'state/profile.json').read_text(encoding='utf-8'))
    if model_name:profile.model_name=model_name
    if Path(profile.source_root).resolve()!=repository/'bank-demo/composer/Workspace':raise ValueError('Only bank-demo is supported')
    profile.executable_verification.mode='executable_boundary_v1';profile.staged_unit_conversion=True;profile.side_road_conversion=False
    profile.executable_verification.require_branch_coverage=True
    profile.executable_verification.comparison_mutations.enabled=True
    profile.enable_git=False;profile.output_root=str(output);profile.channels=['INTERNET'];profile.include_operations=['GetClientLinksOp']
    require_model_readiness(profile)
    output.mkdir(parents=True)
    report=dict(status='preparing',operation=OPERATION,units={},full_operation={'status':'not_run','acceptance_complete':False},
        rollout_ready=False,default_changed=False,verification_mode=profile.executable_verification.mode)
    if prior_trials:
        from tools.behavior_verification.acceptance_trial_state import inherit_provider_attempts
        report['attempt_provenance']=inherit_provider_attempts(Path(prior_trials).resolve(),output)
    publish(output,report)
    (output/'process.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        model_name=profile.model_name,model_timeout_seconds=profile.model_timeout_seconds,log='trials.log',error_log='trials-errors.log'),indent=2))
    handlers=[logging.FileHandler(output/'trials.log',encoding='utf-8'),logging.FileHandler(output/'trials-errors.log',encoding='utf-8')]
    handlers[1].setLevel(logging.ERROR)
    for handler in handlers:
        handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'));logging.getLogger().addHandler(handler)
    conn=get_connection(str(output/'trials.db'));create_all_tables(conn)
    config=SimpleNamespace(run_id='bank-executable-acceptance',output_root=str(output));upsert_run(conn,run_id=config.run_id,run_mode='acceptance_trials')
    try:
        preparation,units,fresh=load_trial_inputs(input_run)
        with java_scope(profile):
            subset=dict(run_id=config.run_id,operations={OPERATION:dict(behavior_request=preparation['operations'][OPERATION]['behavior_request'],units=units)})
            boundaries=build_boundary_report(subset)
            for unit in units:
                name=unit['logical_id'];report.update(status='running_boundaries',current_unit=name);publish(output,report)
                try:
                    fresh();boundary=UnitVerificationBoundary.model_validate(boundaries['boundaries'][unit['unit_id']])
                    answers=UnitChecklistAnswers(unit_id=unit['unit_id'],source_manifest_hash=boundary.source_manifest_hash,configuration_hash=boundary.configuration_hash)
                    analysis,_=inspect_static_sources(unit,boundary,{},answers,profile.unit_verification_policy)
                    request,instruction=build_request(unit,boundary,analysis.get('settings',[]),profile)
                    configured=dict(request['selected_unit'])
                    request.update(kind=unit['kind'],unit=configured)
                    request['configured_unit' if unit['kind']=='configured_step' else 'configured_format']=configured
                    session=UnitVerificationSession(config,unit,boundary,tool=default_tool_path(),policy=profile.unit_verification_policy,
                        executable_settings=profile.executable_verification)
                    validator=AcceptanceTrialValidator(session,profile,request,output/name/'candidate',fresh)
                    if prior_trials:
                        from tools.behavior_verification.acceptance_trial_state import enforce_inherited_budget
                        validator.implementation_attempt=lambda:enforce_inherited_budget(conn,config.run_id,unit['unit_id'],profile.max_agent_task_retries)
                    with verification_session(session):
                        generate(conn,config,profile,'unit',unit['unit_id'],instruction,request,NativeUnitBundle,validator,label=name)
                    receipt=record_verification(conn,config,unit['unit_id'],'accepted',session.last_report)
                    strength=receipt.get('comparison_strength',{})
                    defect=strength.get('status')=='completed' and strength.get('counts',{}).get('detected',0)>0
                    report['units'][name]=dict(status='accepted',observed_cases=receipt['observed_cases'],evidence=receipt['evidence'],
                        defect_check='passed' if defect else 'incomplete',comparison_strength=strength)
                except Exception as error:
                    report['units'][name]=dict(status='verification_incomplete' if isinstance(error,VerificationIncomplete) else 'failed',
                        error=sanitize_diagnostic(str(error)),failure_type=type(error).__name__)
                    logging.getLogger(__name__).exception('Boundary trial stopped: %s',name)
                publish(output,report)
        if boundaries_passed(report):
            report['status']='running_full_operation';publish(output,report)
            full=output/'full-operation';data=profile.model_dump(mode='json')
            (output/'full-operation-profile.yaml').write_text(yaml.safe_dump(data),encoding='utf-8')
            from tools.behavior_verification.component_pilot_run import run_fresh
            run_fresh(output/'full-operation-profile.yaml',full,'single-get-client-links')
            report['full_operation']=json.loads((full/'cf8-measurement.json').read_text(encoding='utf-8'))
        report['rollout_ready']=rollout_ready(report)
        report['status']='passed' if report['rollout_ready'] else 'blocked'
    except Exception as error:
        report.update(status='blocked',error=sanitize_diagnostic(str(error)),failure_type=type(error).__name__)
        logging.getLogger(__name__).exception('Acceptance trial preflight or full operation stopped')
    finally:
        publish(output,report);conn.close()
        for handler in handlers:logging.getLogger().removeHandler(handler);handler.close()
    return 0 if report['rollout_ready'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input-run',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--model-name');parser.add_argument('--prior-trials')
    args=parser.parse_args()
    handler=logging.StreamHandler();handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    raise SystemExit(run(args.input_run,args.output,model_name=args.model_name,prior_trials=args.prior_trials))
