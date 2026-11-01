"""Run three real bank-demo boundaries in isolated experiment state; fail fast, never accept an operation."""
import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from models.pipeline_configuration import PipelineConfiguration
from models.common_models.common import RunConfig
from models.native_unit_bundle import NativeUnitBundle
from models.unit_verification_boundary import UnitVerificationBoundary
from models.unit_checklist_answers import UnitChecklistAnswers
from runtime.java_toolchain import java_scope
from runtime.model_execution.error_details import SafeDiagnosticFormatter
from runtime.behavior_conversion.generation import generate
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.behavior_units import initialize
from tools.behavior_verification.thin_path_request import OPERATION, select_units, build_request
from tools.behavior_verification.thin_path_validation import ThinPathValidator
from tools.behavior_verification.boundaries import build_boundary_report
from tools.behavior_verification.static_analysis import inspect_static_sources
from tools.behavior_verification.java_tool import default_tool_path
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.behavior_evidence_freshness import verify_configuration_sources


def publish(base, report):
    """Write experiment progress atomically; no production acceptance flags are inferred."""
    report['recorded_at'] = datetime.now(timezone.utc).isoformat()
    path = base/'thin-path-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    temporary.replace(path)


def run(input_run, output, *, model_call=None, factory=None, replay_database=None, replay_attempt=3, replay_unit='GetClientLinksRQFmt',
        correction_database=None,correction_report=None,continue_on_failure=False,side_road=False,only_unit=None,model_name=None,
        staged=False,model_timeout_seconds=None):
    """Reuse read-only bank Mapper evidence, with a new three-unit model/build/comparison experiment."""
    input_run, output = Path(input_run).resolve(), Path(output).resolve()
    if replay_database and correction_database:raise ValueError('Replay and model correction are separate experiment modes')
    if bool(correction_database)!=bool(correction_report):raise ValueError('Correction needs both saved database and comparison report')
    repository = Path(__file__).resolve().parents[3]
    if not output.is_relative_to(repository/'outputs'):
        raise ValueError('Thin-path output must be a fresh directory under repository outputs')
    profile = PipelineConfiguration.model_validate_json((input_run/'state/profile.json').read_text(encoding='utf-8'))
    if model_name:
        profile.model_name = model_name
    if model_timeout_seconds is not None:
        if model_timeout_seconds<=0:raise ValueError('Model timeout must be positive')
        profile.model_timeout_seconds=model_timeout_seconds
    profile.staged_unit_conversion=staged
    if Path(profile.source_root).resolve() != repository/'bank-demo/composer/Workspace':
        raise ValueError('This experiment accepts only the repository bank demo')
    preparation = json.loads(next((input_run/'reports').rglob('scoped_workflow_preparation.json')).read_text(encoding='utf-8'))
    units = select_units(preparation)
    if only_unit:
        units=[unit for unit in units if unit['logical_id']==only_unit]
        if len(units)!=1:raise ValueError('Requested unit is not in the selected thin path')
    profile.side_road_conversion = side_road
    if replay_database:
        units=[unit for unit in units if unit['logical_id']==replay_unit]
        if len(units)!=1:raise ValueError('Replay unit is not in the selected thin path')
    original = sqlite3.connect((input_run/'state/migration.db').as_uri()+'?mode=ro', uri=True)
    original.row_factory = sqlite3.Row
    metadata = original.execute('SELECT run_config_json FROM runs WHERE run_id=?', (preparation['run_id'],)).fetchone()
    if metadata is None:
        raise ValueError('Original run metadata is missing')
    original_config = RunConfig.model_validate_json(metadata[0])
    origins = {item.get('definition_id'): item for item in preparation['operations'][OPERATION]['behavior_request']['java_origins']}
    def fresh():
        verify_configuration_sources(original, original_config, 'GetClientLinksOp', 'INTERNET')
        for unit in units:
            for source in unit['sources']:
                origin = origins.get(source['identity'])
                if origin is None or origin['status'] != 'verified_source' or origin['source_hash'] != source['content_hash'] or (
                    file_digest(Path(origin['source_file'])) != source['content_hash'] or
                    Path(origin['source_file']).read_text(encoding='utf-8-sig') != source['content']):
                    raise ValueError('Original source evidence changed: ' + source['identity'])
    fresh()
    output.mkdir(parents=True, exist_ok=False)
    profile.enable_git = False
    profile.output_root = str(output)
    report = dict(status='running', operation=OPERATION, experiment_only=True, full_operation_accepted=False,
        production_units_accepted=0, selected_units=[unit['logical_id'] for unit in units], units={},
        pending_units=[unit['logical_id'] for unit in units], failed_units=[], incomplete_units=[], observed_matches=0,
        acceptance_policy='Build, executed tests and observed boundary equality only; unresolved paths remain reported, not proven.')
    (output/'process.json').write_text(json.dumps(dict(pid=os.getpid(), started_at=datetime.now(timezone.utc).isoformat(),
        input_run=str(input_run), model_name=profile.model_name, model_timeout_seconds=profile.model_timeout_seconds,
        staged_unit_conversion=profile.staged_unit_conversion, log='experiment.log', error_log='experiment-errors.log'), indent=2), encoding='utf-8')
    handlers = [logging.FileHandler(output/'experiment.log', encoding='utf-8'),
                logging.FileHandler(output/'experiment-errors.log', encoding='utf-8')]
    handlers[1].setLevel(logging.ERROR)
    for handler in handlers:
        handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        logging.getLogger().addHandler(handler)
    conn = get_connection(str(output/'experiment.db'))
    create_all_tables(conn); initialize(conn)
    config = SimpleNamespace(run_id='bank-thin-path', output_root=str(output))
    upsert_run(conn, run_id=config.run_id, run_mode='thin_path_experiment')
    publish(output, report)
    try:
        with java_scope(profile):
            subset = dict(run_id=config.run_id, operations={OPERATION: dict(
                behavior_request=preparation['operations'][OPERATION]['behavior_request'], units=units)})
            boundaries = build_boundary_report(subset)
            (output/'boundaries.json').write_text(json.dumps(boundaries, indent=2), encoding='utf-8')
            accepted_types = []
            for unit in units:
                name = unit['logical_id']
                report['current_unit'] = name
                report['stage'] = 'generation_build_comparison'
                publish(output, report)
                boundary = UnitVerificationBoundary.model_validate(boundaries['boundaries'][unit['unit_id']])
                if boundary.analysis_status != 'identified' or boundary.parser_checklist is None:
                    raise ValueError('Original boundary could not be identified: ' + name)
                answers = UnitChecklistAnswers(unit_id=unit['unit_id'], source_manifest_hash=boundary.source_manifest_hash,
                    configuration_hash=boundary.configuration_hash)
                analysis, _ = inspect_static_sources(unit, boundary, {}, answers, profile.unit_verification_policy)
                controls = analysis.get('settings', [])
                request, instruction = build_request(unit, boundary, controls, profile,
                    correcting=bool(correction_database and name==replay_unit), accepted=accepted_types)
                validator = ThinPathValidator(unit, boundary, controls, request, profile, output/name, fresh,
                                               tool=default_tool_path(), factory=factory)
                try:
                    if replay_database:
                        from tools.behavior_verification.thin_path_saved_candidate import read_candidate
                        bundle,saved=read_candidate(replay_database,replay_attempt,unit)
                        report['replay']=saved
                        publish(output,report)
                        validator(bundle)
                    else:
                        if correction_database and name==replay_unit:
                            from tools.behavior_verification.thin_path_correction import seed_correction
                            request,saved=seed_correction(request,correction_database,replay_attempt,unit,correction_report)
                            report['correction_seed']=saved
                            publish(output,report)
                            instruction+='\nCorrect only the supplied actual input/value differences using original evidence. Preserve other behavior. Comparison limitations are not code-correction requests.'
                        bundle, _ = generate(conn, config, profile, 'thin_path_experiment', unit['unit_id'], instruction, request,
                            NativeUnitBundle, validator=validator, model_call=model_call, label='Thin path: '+name)
                    report['units'][name] = validator.last
                    report['pending_units'].remove(name)
                    report['observed_matches'] += 1
                    accepted_types.append(dict(unit_id=unit['unit_id'], apis=[api.model_dump(mode='json') for api in bundle.unit_contract.apis],
                        files=[file.model_dump(mode='json') for file in bundle.files if file.path.startswith('src/main/java/')],
                        dependencies=[item.model_dump(mode='json') for item in bundle.dependencies]))
                except Exception as failure:
                    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
                    report['units'][name] = validator.last or dict(status='generation_or_static_validation_failed')
                    report['pending_units'].remove(name)
                    report['incomplete_units' if isinstance(failure,VerificationIncomplete) else 'failed_units'].append(name)
                    report['units'][name]['error']=str(failure)
                    publish(output,report)
                    if not continue_on_failure:raise
                publish(output, report)
            report.update(status='blocked' if report['failed_units'] else 'verification_incomplete' if report['incomplete_units'] else
                'matched_observed_cases', stage='finished', exhaustive_equivalence=False)
    except Exception as error:
        from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
        logging.getLogger(__name__).exception('Thin-path experiment stopped')
        report.update(status='verification_incomplete' if isinstance(error,VerificationIncomplete) else 'blocked', error=str(error))
    finally:
        publish(output, report)
        original.close(); conn.close()
        for handler in handlers:
            logging.getLogger().removeHandler(handler); handler.close()
    return report


def main(argv=None):
    """Run only the named thin path; existing scoped runs and their acceptance state stay untouched."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-run', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--replay-database')
    parser.add_argument('--replay-attempt',type=int,default=3)
    parser.add_argument('--replay-unit',default='GetClientLinksRQFmt')
    parser.add_argument('--correction-database')
    parser.add_argument('--correction-report')
    parser.add_argument('--continue-on-failure',action='store_true')
    parser.add_argument('--side-road',action='store_true')
    parser.add_argument('--only-unit',choices=['GetClientLinksRQFmt','StandardErrorRSFmt','NoLinksFound'])
    parser.add_argument('--model-name')
    parser.add_argument('--staged',action='store_true')
    parser.add_argument('--model-timeout-seconds',type=int)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    return 0 if run(args.input_run,args.output,replay_database=args.replay_database,
        replay_attempt=args.replay_attempt,replay_unit=args.replay_unit,correction_database=args.correction_database,
        correction_report=args.correction_report,continue_on_failure=args.continue_on_failure,
        side_road=args.side_road,only_unit=args.only_unit,model_name=args.model_name,staged=args.staged,
        model_timeout_seconds=args.model_timeout_seconds)['status']=='matched_observed_cases' else 1


if __name__ == '__main__':
    raise SystemExit(main())
