"""Replay one fingerprint-verified implementation request with only the model changed."""
import argparse
import hashlib
import json
import logging
import os
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from models.pipeline_configuration import PipelineConfiguration
from models.native_unit_bundle import NativeUnitBundle
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.java_toolchain import java_scope
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.error_details import SafeDiagnosticFormatter,sanitize_diagnostic
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.verification_ladder import UnitVerificationSession,verification_session
from tools.behavior_verification.frozen_model_request import read_request
from tools.behavior_verification.bank_trial_inputs import load_trial_inputs
from tools.behavior_verification.thin_path_request import OPERATION,build_request
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.acceptance_trial_validation import AcceptanceTrialValidator
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run


class ComparisonFinished(ValueError):
    """Further stages/corrections are outside this single-request controlled comparison."""


def run(input_run,prior,output,model_name,*,saved_response=None):
    """Keep production prompts/validators untouched and isolate the explicitly requested extra call."""
    repository=Path(__file__).resolve().parents[3]
    input_run,prior,output=map(lambda path:Path(path).resolve(),(input_run,prior,output))
    if not output.is_relative_to(repository/'outputs') or output.exists():raise ValueError('Use fresh repository outputs for the comparison')
    profile=PipelineConfiguration.model_validate_json((input_run/'state/profile.json').read_text(encoding='utf-8'))
    baseline_model=json.loads((prior/'process.json').read_text())['model_name'];profile.model_name=baseline_model
    frozen=read_request(prior,profile,'GetClientLinksRQFmt')
    output.mkdir(parents=True)
    for name,text in [('instruction.txt',frozen['instruction']),('request.json',frozen['payload']),('lite-response.json',frozen['response'])]:
        (output/name).write_text(text,encoding='utf-8')
    report=dict(status='preparing',baseline_model=baseline_model,model_name=model_name,scope='single_initial_implementation_request',
        original_fingerprint=frozen['fingerprint'],prompt_hash=hashlib.sha256(frozen['instruction'].encode()).hexdigest(),
        payload_hash=hashlib.sha256(frozen['payload'].encode()).hexdigest(),baseline_rejection=frozen['error'],
        logical_provider_calls=0,unit_accepted=False,junit_run=False,output_comparison_run=False)
    report['typed_boundary_acceptance_validated']=False
    report['response_deliveries']=0
    if saved_response:
        saved_response=Path(saved_response).resolve()
        report.update(scope='saved_response_validation',saved_response=str(saved_response),saved_response_hash=hashlib.sha256(saved_response.read_bytes()).hexdigest())
    def save():
        path=output/'model-comparison.json.tmp';path.write_text(json.dumps(report,indent=2),encoding='utf-8');path.replace(output/'model-comparison.json')
    save()
    (output/'process.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        model_name=model_name,model_timeout_seconds=profile.model_timeout_seconds,log='comparison.log'),indent=2))
    handler=logging.FileHandler(output/'comparison.log',encoding='utf-8');handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(handler)
    profile.model_name=model_name;profile.output_root=str(output);profile.enable_git=False
    profile.staged_unit_conversion=True;profile.side_road_conversion=False
    profile.executable_verification.mode='executable_boundary_v1';profile.executable_verification.require_branch_coverage=True
    profile.executable_verification.comparison_mutations.enabled=True
    conn=get_connection(str(output/'comparison.db'));create_all_tables(conn)
    config=SimpleNamespace(run_id='controlled-model-comparison',output_root=str(output));upsert_run(conn,run_id=config.run_id,run_mode='model_comparison')
    def model(prompt,payload):
        if report['response_deliveries']:raise ComparisonFinished('No additional request or correction is permitted in the paired comparison')
        if prompt!=frozen['instruction'] or json.loads(payload)!=frozen['request']:
            raise ValueError('Current staged request differs from the fingerprint-verified Lite request')
        report.update(status='validating_implementation' if saved_response else 'calling_model',logical_provider_calls=0 if saved_response else 1,
            response_deliveries=1,prompt_unchanged=True,payload_unchanged=True);save()
        if saved_response:
            response=saved_response.read_text(encoding='utf-8')
            (output/'response.json').write_bytes(saved_response.read_bytes())
        else:
            response=AdkExecutor(profile).execute(frozen['instruction'],frozen['payload'])
            (output/'response.json').write_text(response,encoding='utf-8')
        report['status']='validating_implementation';save();return response
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
            with verification_session(session):
                generate(conn,config,profile,'unit',unit['unit_id'],instruction,payload,NativeUnitBundle,validator,model_call=model)
    except Exception as error:report['stop_reason']=sanitize_diagnostic(str(error))
    finally:
        proof=conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE stage='compile'").fetchone()
        report['production_compile']=json.loads(proof[0])['validation'] if proof and proof[0] else None
        response_returned=(output/'response.json').is_file()
        errors=conn.execute("SELECT error FROM behavior_attempts WHERE category='staged_implementation' AND response IS NOT NULL").fetchall()
        report['implementation_errors']=[row[0] for row in errors if row[0]]
        report['status']=('implementation_passed' if report['production_compile'] and report['production_compile'].get('build_passed')
            else 'implementation_rejected' if response_returned else 'no_model_response' if report['logical_provider_calls'] else 'setup_blocked')
        save();conn.close();logging.getLogger().removeHandler(handler);handler.close()
    return 0 if report['status']=='implementation_passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input-run','prior','output','model-name'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--saved-response')
    args=parser.parse_args();handler=logging.StreamHandler();handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    raise SystemExit(run(args.input_run,args.prior,args.output,args.model_name,saved_response=args.saved_response))
