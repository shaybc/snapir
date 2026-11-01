"""Record advisory PIT results after technical acceptance without changing that decision."""
import hashlib
import json
import logging
from pathlib import Path
from tools.behavior_verification.mutation_snapshot import snapshot_project, PIT_VERSION, JUNIT_PLUGIN_VERSION
from tools.behavior_verification.mutation_results import read_mutations
from tools.behavior_verification.mutation_execution import run_mutations
from tools.maven_dependency_tools.command import maven_executable


def prepare_measurement(session, project, bundle):
    """Retain the staged project before the existing publication flow cleans it up."""
    if session.mutation_settings is None or not session.mutation_settings.enabled: return
    session.strength_directory = session.attempt / 'test-strength'
    session.strength_error = None
    try:
        session.strength_inputs = snapshot_project(project, session.strength_directory / 'project', bundle)
    except Exception as error:
        session.strength_error = str(error)


def measure_accepted_unit(session, profile, receipt):
    """A missing tool, low score or timeout is an advisory report, never a failed unit."""
    settings = session.mutation_settings
    directory = getattr(session, 'strength_directory', session.attempt / 'test-strength')
    report = dict(schema_version='unit-test-strength-v1', unit_id=session.unit['unit_id'], advisory=True,
        affects_acceptance=False, exhaustive_equivalence=False, candidate_hash=receipt['candidate_hash'],
        source_manifest_hash=receipt['source_manifest_hash'], configuration_hash=receipt['configuration_hash'],
        pit_version=PIT_VERSION, junit_plugin_version=JUNIT_PLUGIN_VERSION,
        recommended_score=settings.recommended_score, status='disabled', score=None)
    report['report_directory'] = str(directory.resolve())
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if settings.enabled:
            if getattr(session, 'strength_error', None): raise ValueError(session.strength_error)
            report['inputs'] = session.strength_inputs
            project = directory / 'project'
            command = [maven_executable(), '--batch-mode']
            if profile.maven_settings_path: command.extend(['--settings', profile.maven_settings_path])
            if profile.maven_local_repository: command.append('-Dmaven.repo.local=' + profile.maven_local_repository)
            command.extend(['test-compile', 'org.pitest:pitest-maven:' + PIT_VERSION + ':mutationCoverage'])
            report['command'] = command
            from runtime.java_toolchain import java_environment
            code, output, timed_out = run_mutations(command, project, settings.timeout_seconds,
                java_environment(profile.java_version, profile.java_home))
            from runtime.model_execution.error_details import sanitize_diagnostic
            (directory / 'maven.log').write_text(sanitize_diagnostic(output), encoding='utf-8')
            report.update(return_code=code, status='timed_out' if timed_out else 'tool_error')
            if code == 0 and not timed_out:
                raw = directory / 'pit-reports/mutations.xml'
                report.update(read_mutations(raw, settings.recommended_score))
                report['raw_report_hash'] = hashlib.sha256(raw.read_bytes()).hexdigest()
            else:
                report['recommendations'] = ['Resolve PIT availability/execution before measuring test strength; acceptance is unchanged.']
        _save(directory, report)
    except Exception as error:
        report.update(status='tool_error', error=str(error), score=None)
        try: _save(directory, report)
        except Exception: logging.getLogger(__name__).exception('Could not save advisory test-strength report')
    return report


def _save(directory, report):
    temporary = directory / 'test-strength.json.tmp'
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
    temporary.replace(directory / 'test-strength.json')
