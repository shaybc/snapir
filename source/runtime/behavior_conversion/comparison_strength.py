"""Run advisory differential mutation measurement with a process-tree wall-clock budget."""
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from runtime.java_toolchain import java_environment,java_version
from tools.behavior_verification.mutation_execution import run_mutations
from tools.behavior_verification.comparison_mutations import VERSION,save_measurement


def measure_comparisons(session,native,legacy,cases,tool,*,owned_paths=None):
    """Keep measurement failures advisory; only disposable snapshots enter the worker."""
    settings=session.executable_settings.comparison_mutations
    if not settings.enabled:return None
    directory=session.attempt/'comparison-strength'
    report=dict(schema_version=VERSION,status='tool_failure',advisory=True,affects_acceptance=False,exhaustive=False)
    try:
        directory.mkdir()
        environment=java_environment() or os.environ.copy()
        environment['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
        environment['PYTHONDONTWRITEBYTECODE']='1'
        sources={file.path:hashlib.sha256(file.content.encode()).hexdigest() for file in native.sources}
        job=dict(unit=session.unit,boundary=session.boundary.model_dump(mode='json'),native=native.model_dump(mode='json'),
            legacy=legacy.model_dump(mode='json'),cases=[case.model_dump(mode='json') for case in cases],tool=str(Path(tool).resolve()),
            max_mutants=settings.max_mutants,java_version=int(java_version()),java_home=environment.get('JAVA_HOME'),candidate_sources=sources,
            owned_paths=owned_paths)
        baseline=session.attempt/'comparison/boundary-comparison.json'
        if baseline.is_file():
            raw=baseline.read_bytes();baseline_data=json.loads(raw)
            digest=hashlib.sha256(raw).hexdigest()
            if digest==(getattr(session,'last_report',None) or {}).get('report_hash'):
                job.update(verified_baseline=dict(path=str(baseline.resolve()),sha256=digest),
                    execution_cwd=baseline_data['execution_environment'].get('working_directory',os.getcwd()))
        path=directory/'job.json';path.write_text(json.dumps(job),encoding='utf-8')
        code,output,timed_out=run_mutations([sys.executable,'-B','-m','tools.behavior_verification.comparison_mutations',str(path.resolve())],
            directory,settings.timeout_seconds,environment)
        from runtime.model_execution.error_details import sanitize_diagnostic
        (directory/'worker.log').write_text(sanitize_diagnostic(output),encoding='utf-8')
        saved=directory/'comparison-strength.json'
        if saved.is_file():
            retained=json.loads(saved.read_text(encoding='utf-8'))
            if not isinstance(retained,dict):raise ValueError('Invalid comparison-strength report')
            report=retained
        if timed_out or code!=0 or report.get('status')=='running':
            report['status']='timed_out' if timed_out else 'tool_failure'
            for entry in report.get('mutations',[]):
                if entry['status']=='running':
                    entry['status']='tool_failure';report['counts']['tool_failure']+=1
        report.update(timeout_seconds=settings.timeout_seconds,return_code=code,candidate_hash=session.executable_structure['candidate_hash'])
        report['pending_mutants']=max(0,report.get('planned_mutants',0)-len(report.get('mutations',[])))
        save_measurement(directory,report)
    except Exception as error:
        report.update(status='tool_failure',error=str(error))
        try:save_measurement(directory,report)
        except OSError:logging.getLogger(__name__).exception('Could not save advisory comparison-strength report')
    saved=directory/'comparison-strength.json'
    try:digest=hashlib.sha256(saved.read_bytes()).hexdigest() if saved.is_file() else None
    except OSError:digest=None
    return dict(status=report['status'],advisory=True,affects_acceptance=False,evidence=str(directory/'comparison-strength.json'),
        report_hash=digest,counts=report.get('counts',{}))
