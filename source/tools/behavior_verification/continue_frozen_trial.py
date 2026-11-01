"""Continue details, adapter and tests on frozen compiled bank code; never regenerate implementation."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
from runtime.configuration import load_configuration
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeUnitBundle
from models.native_implementation import NativeImplementation
from models.native_test_bundle import NativeTestBundle
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.java_toolchain import java_scope
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession,verification_session
from runtime.behavior_conversion.verification_state import record_verification
from tools.behavior_verification.bank_trial_inputs import load_trial_inputs
from tools.behavior_verification.frozen_trial_state import load_compiled_candidate,copy_stage_state
from tools.behavior_verification.thin_path_request import OPERATION,build_request
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.acceptance_trial_validation import AcceptanceTrialValidator
from tools.state_store_tools.db import get_connection


def run(input_run,prior,output,profile_path,*,resume_state=None,corrected_implementation=None,corrected_tests=None):
    """Use retained budgets and freeze original or explicitly supplied corrected production bytes."""
    input_run,prior,output=map(lambda value:Path(value).resolve(),(input_run,prior,output))
    if output.exists() or not output.is_relative_to(Path(__file__).resolve().parents[3]/'outputs'):
        raise ValueError('Use a fresh repository outputs directory')
    selected=load_configuration(profile_path)
    if selected.executable_verification.mode!='executable_boundary_v1':raise ValueError('Select executable_boundary_v1 for these trials')
    production,origin=load_compiled_candidate(prior)
    from tools.component_inventory_tools.identity import stable_id
    if corrected_implementation:
        production=NativeImplementation.model_validate_json(Path(corrected_implementation).read_text(encoding='utf-8'))
        if production.unresolved_questions:raise ValueError('Corrected implementation has unresolved behavior')
    frozen_hash=stable_id(production.model_dump(mode='json'))
    supplied_tests=NativeTestBundle.model_validate_json(Path(corrected_tests).read_text(encoding='utf-8')) if corrected_tests else None
    profile=PipelineConfiguration.model_validate_json((input_run/'state/profile.json').read_text())
    profile.model_name=selected.model_name;profile.staged_unit_conversion=selected.staged_unit_conversion
    profile.side_road_conversion=False;profile.enable_git=False;profile.output_root=str(output)
    profile.executable_verification.mode=selected.executable_verification.mode
    profile.executable_verification.require_branch_coverage=True;profile.executable_verification.comparison_mutations.enabled=True
    profile.executable_verification.comparison_mutations.timeout_seconds=selected.executable_verification.comparison_mutations.timeout_seconds
    if resume_state:
        resume_state=Path(resume_state).resolve()
        previous=json.loads((resume_state/'continuation.json').read_text())
        if previous.get('status') not in {'failed','verification_incomplete'} or previous['origin']['implementation_hash']!=origin['implementation_hash']:
            raise ValueError('Resume state does not belong to this stopped frozen candidate')
        resume_hash=hashlib.sha256((resume_state/'continuation.db').read_bytes()).hexdigest()
    output.mkdir(parents=True)
    copy_stage_state(resume_state or prior,output/'continuation.db',database='continuation.db' if resume_state else 'comparison.db')
    report=dict(status='preparing',model_name=profile.model_name,verification_mode=profile.executable_verification.mode,
        implementation_frozen=True,implementation_regeneration_allowed=False,origin=origin,new_model_calls={},unit_accepted=False)
    report.update(frozen_implementation_hash=frozen_hash,corrected_implementation=str(corrected_implementation) if corrected_implementation else None)
    if supplied_tests:report.update(corrected_tests=str(corrected_tests),supplied_test_hash=stable_id(supplied_tests.model_dump(mode='json')))
    if resume_state:report.update(resume_state=str(resume_state),resume_database_hash=resume_hash)
    def save():
        path=output/'continuation.json.tmp';path.write_text(json.dumps(report,indent=2),encoding='utf-8');path.replace(output/'continuation.json')
    save();(output/'profile.json').write_text(profile.model_dump_json(indent=2))
    (output/'process.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        model_name=profile.model_name,model_timeout_seconds=profile.model_timeout_seconds,log='continuation.log'),indent=2))
    handler=logging.FileHandler(output/'continuation.log',encoding='utf-8');handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(handler)
    conn=get_connection(str(output/'continuation.db'));config=SimpleNamespace(run_id='controlled-model-comparison',output_root=str(output))
    executor=AdkExecutor(profile)
    def model(prompt,payload):
        title=json.loads(payload)['schema']['title']
        if title=='NativeImplementation':raise VerificationIncomplete(dict(stage='frozen_implementation',errors=['Implementation generation is forbidden']))
        report['status']='generating_'+title;report['new_model_calls'][title]=report['new_model_calls'].get(title,0)+1;save()
        return executor.execute(prompt,payload)
    try:
        preparation,units,fresh=load_trial_inputs(input_run)
        unit=next(unit for unit in units if unit['logical_id']=='GetClientLinksRQFmt')
        with java_scope(profile):
            boundaries=build_boundary_report(dict(run_id=config.run_id,operations={OPERATION:dict(
                behavior_request=preparation['operations'][OPERATION]['behavior_request'],units=[unit])}))
            boundary=UnitVerificationBoundary.model_validate(boundaries['boundaries'][unit['unit_id']])
            answers=UnitChecklistAnswers(unit_id=unit['unit_id'],source_manifest_hash=boundary.source_manifest_hash,configuration_hash=boundary.configuration_hash)
            analysis,_=inspect_static_sources(unit,boundary,{},answers,profile.unit_verification_policy)
            payload,instruction=build_request(unit,boundary,analysis.get('settings',[]),profile)
            configured=dict(payload['selected_unit']);payload.update(kind=unit['kind'],unit=configured,configured_format=configured)
            session=UnitVerificationSession(config,unit,boundary,tool=default_tool_path(),policy=profile.unit_verification_policy,executable_settings=profile.executable_verification)
            validator=AcceptanceTrialValidator(session,profile,payload,output/'candidate',fresh)
            validator.frozen_implementation=production;validator.frozen_implementation_hash=frozen_hash
            if supplied_tests is not None:validator.frozen_tests=supplied_tests
            with verification_session(session):
                bundle,_=generate(conn,config,profile,'unit',unit['unit_id'],instruction,payload,NativeUnitBundle,validator,model_call=model)
            report['receipt']=record_verification(conn,config,unit['unit_id'],'accepted',session.last_report)
            report.update(status='accepted',unit_accepted=True)
    except Exception as error:
        report.update(status='verification_incomplete' if isinstance(error,VerificationIncomplete) else 'failed',error=sanitize_diagnostic(str(error)),failure_type=type(error).__name__)
        logging.getLogger(__name__).exception('Frozen acceptance continuation stopped')
    finally:
        files=[f.model_dump(mode='json') for f in production.files]
        from tools.component_inventory_tools.identity import stable_id
        report['implementation_unchanged']=stable_id(production.model_dump(mode='json'))==frozen_hash
        report['implementation_matches_original']=frozen_hash==origin['implementation_hash']
        report['original_database_unchanged']=hashlib.sha256((prior/'comparison.db').read_bytes()).hexdigest()==origin['database_hash']
        if resume_state:report['resume_database_unchanged']=hashlib.sha256((resume_state/'continuation.db').read_bytes()).hexdigest()==resume_hash
        report['passing_tests_retained']=bool(conn.execute("SELECT 1 FROM staged_conversion_tasks WHERE stage='passing_tests' AND artifact_json IS NOT NULL").fetchone())
        (output/'frozen-files.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
        save();conn.close();logging.getLogger().removeHandler(handler);handler.close()
    return 0 if report['unit_accepted'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input-run','prior','output','profile'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--resume-state')
    parser.add_argument('--corrected-implementation',help='Explicitly authorized replacement production JSON; recompiled and frozen before later stages')
    parser.add_argument('--corrected-tests',help='Explicit saved test correction; validate afresh without a provider call or budget reset')
    args=parser.parse_args();handler=logging.StreamHandler();handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    raise SystemExit(run(args.input_run,args.prior,args.output,args.profile,resume_state=args.resume_state,corrected_implementation=args.corrected_implementation,corrected_tests=args.corrected_tests))
