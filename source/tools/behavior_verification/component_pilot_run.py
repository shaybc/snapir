"""Run a fresh bank-demo Mapper/converter acceptance pilot; never deploy or change Git state."""
import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path
from threading import Event, Thread
from datetime import datetime, timezone
from time import monotonic
from runtime.configuration import load_configuration
from runtime.model_execution.error_details import SafeDiagnosticFormatter, sanitize_diagnostic
from tools.behavior_verification.component_pilot import PilotMetrics, publish_component_run, measure_component_run


def collect_pilot(base, run_id):
    """Reuse the existing source-bound selector/measurement on all available bank units."""
    from runtime.workspace_paths import run_report_path
    from tools.behavior_verification.pilot import main
    directory = base/run_id
    prep = run_report_path(directory,'scoped_workflow_preparation.json')
    boundaries = run_report_path(directory,'behavior_verification_boundaries.json')
    if not prep.is_file() or not boundaries.is_file():
        return
    sample = base/'pilot-sample.json'
    main(['select','--preparation',str(prep),'--boundaries',str(boundaries),'--dataset-type','bank_demo',
        '--per-group','1000','--output',str(sample)])
    main(['report','--sample',str(sample),'--database',str(directory/'state/migration.db'),
        '--run-id',run_id,'--run-output',str(directory/'generated'),'--output',str(base/'pilot-measurement.json')])


def process_alive(pid):
    """Query process liveness without signalling or terminating it, including on Windows."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            return False
        try:
            code=wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code)) and code.value==259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid,0)
        return True
    except ProcessLookupError:
        return False


def run_fresh(profile_path, base, run_id, *, warm_reuse=True, resume=False):
    """Retain durable process identity/status and compare reuse only after full cold acceptance."""
    from runtime.pipeline_runner import run_pipeline
    from runtime.checkpoints import resume_pipeline
    from runtime.java_toolchain import resolve_java_home
    from runtime.model_execution.readiness import require_model_readiness
    repository = Path(__file__).resolve().parents[3]
    base = Path(base).resolve()
    from runtime.workspace_paths import resolve_run_directory,run_profile_path
    directory=resolve_run_directory(str(base),run_id)
    previous=None
    if resume:
        from models.pipeline_configuration import PipelineConfiguration
        previous=json.loads((base/'continuation-pid.json').read_text(encoding='utf-8'))
        if previous['run_directory']!=run_id or process_alive(previous['pid']):
            raise ValueError('Resume requires the same stopped CF8 run; its current process must have exited')
        profile=PipelineConfiguration.model_validate_json(run_profile_path(directory).read_text(encoding='utf-8'))
        if profile.scoped_native_mode!='component_first_v1':
            raise ValueError('Resume cannot reinterpret a different conversion mode')
    else:
        profile = load_configuration(profile_path)
    if Path(profile.source_root).resolve() != (repository/'bank-demo/composer/Workspace').resolve():
        raise ValueError('This CF8 pilot accepts only the repository bank-demo workspace')
    if not base.is_relative_to((repository/'outputs').resolve()):
        raise ValueError('CF8 output must be an isolated directory under repository outputs')
    profile.output_root = str(base)
    profile.java_home = resolve_java_home(profile.java_version,profile.java_home)
    profile.scoped_native_mode = 'component_first_v1'
    profile.staged_unit_conversion = True
    profile.behavior_context_chars = 900000
    profile.max_model_attempts = profile.max_agent_task_retries = 4
    profile.plan_approval_policy = 'automatic'
    profile.gate_policies = {str(number):'automatic' for number in range(1,5)}
    profile.enable_git = False
    profile.service_registry_path = str(base/'service-registry.sqlite')
    require_model_readiness(profile)
    base.mkdir(parents=True,exist_ok=resume)
    logs = [logging.FileHandler(base/'conversion.log',encoding='utf-8'),
        logging.FileHandler(base/'conversion-errors.log',encoding='utf-8')]
    logs[1].setLevel(logging.ERROR)
    for handler in logs:
        handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        logging.getLogger().addHandler(handler)
    started = monotonic()
    if previous:
        with (base/'continuation-history.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(previous)+'\n')
    (base/'continuation-pid.json').write_text(json.dumps(dict(pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        initial_started_at=(previous.get('initial_started_at',previous['started_at']) if previous else datetime.now(timezone.utc).isoformat()),
        run_directory=run_id,log='conversion.log',error_log='conversion-errors.log',mode=profile.scoped_native_mode,resumed=resume),indent=2),encoding='utf-8')
    (base/'approval-authorization.json').write_text(json.dumps(dict(
        source='User authorized automatic gates and requested CF8 fresh bank-demo end-to-end validation.',
        automatic_gates=True,technical_checks_preserved=True,manual_review_claimed=False,
        production_pilot=False,git_actions=False,cluster_deployment=False),indent=2),encoding='utf-8')
    metrics = PilotMetrics(base)
    logging.getLogger().addHandler(metrics)
    stop = Event()
    def observe():
        while not stop.wait(15):
            try:
                publish_component_run(base,run_id,running=True)
            except (ValueError,OSError,sqlite3.Error) as error:
                logging.getLogger(__name__).warning('Pilot observer could not publish: %s',sanitize_diagnostic(str(error)))
    observer = Thread(target=observe,name='cf8-evidence-observer',daemon=True)
    observer.start()
    error = None
    try:
        if not resume:
            run_pipeline(profile,run_id)
        publish_component_run(base,run_id,running=True)
        resume_pipeline(str(base),run_id)
    except Exception as exception:
        error = sanitize_diagnostic(type(exception).__name__+': '+str(exception))
        logging.getLogger(__name__).exception('Fresh component-first bank-demo run stopped')
    result = measure_component_run(base,run_id,running=False)
    cold = dict(result,elapsed_seconds=monotonic()-started,error=error)
    (base/'cold-measurement.json').write_text(json.dumps(cold,indent=2),encoding='utf-8')
    if warm_reuse and result['acceptance_complete']:
        try:
            resume_pipeline(str(base),run_id)
            warm = measure_component_run(base,run_id,running=False)
            reuse = dict(status='verified' if warm['acceptance_complete'] else 'incomplete',
                added_model_interactions=warm['model_interactions']-cold['model_interactions'],
                added_transport_attempts=warm['transport_attempts']-cold['transport_attempts'],
                reused_components=warm['reused_components'],accepted_units=warm['accepted_units'],
                accepted_operations=warm['accepted_operations'])
        except Exception as exception:
            error = sanitize_diagnostic(type(exception).__name__+': '+str(exception))
            reuse = dict(status='failed',error=error)
            logging.getLogger(__name__).exception('Warm component-first validation stopped')
    else:
        reuse = dict(status='not_run',reason='Cold end-to-end acceptance is required before measuring unchanged reuse' if warm_reuse else 'Warm check disabled explicitly')
    (base/'reuse-measurement.json').write_text(json.dumps(reuse,indent=2),encoding='utf-8')
    try:
        collect_pilot(base,run_id)
    except Exception as exception:
        logging.getLogger(__name__).exception('Source-bound pilot measurement could not finish')
        error = error or sanitize_diagnostic(type(exception).__name__+': '+str(exception))
    stop.set()
    observer.join(timeout=10)
    result = publish_component_run(base,run_id,running=False,error=error)
    result.update(elapsed_seconds=monotonic()-started,error=error,reuse=reuse)
    if error:
        result['acceptance_complete'] = False
    (base/'continuation-status.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    logging.getLogger().removeHandler(metrics)
    metrics.close()
    for handler in logs:
        logging.getLogger().removeHandler(handler)
        handler.close()
    return 0 if result['acceptance_complete'] and not error and reuse['status']!='failed' else 1


def main(argv=None):
    """Use a new output folder; approved gate policies never weaken technical validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',default='bank-demo/scoped_converter_validation.yaml')
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--run-id',default='bank-demo-component-first')
    parser.add_argument('--no-warm-reuse',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(SafeDiagnosticFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    return run_fresh(args.profile,args.output_root,args.run_id,warm_reuse=not args.no_warm_reuse,resume=args.resume)


if __name__=='__main__':
    raise SystemExit(main())
