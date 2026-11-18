"""CLI/JSON boundary to an independent validator; no validator modules are imported."""
import os
import hashlib
from pathlib import Path
import subprocess
from format_library.configuration import DEFAULTS
from format_library.files import file_hash, write_json
import json
from format_library.progress import WaitProgress, announce, concise, duration


def validate(config, staged, attempt, *, source_roots=(), release=None):
    """Require a complete passing report bound to current file and policy bytes."""
    settings = {**DEFAULTS, **(config or {})}
    policy = Path(settings['validator_policy_path']).resolve()
    report_path = attempt / 'validation.json'
    try:
        release = release if release is not None else settings['target_java_version']
        source_roots = [Path(path).resolve() for path in source_roots]
        support = {'support/' + str(index) + '/' + path.relative_to(root).as_posix(): file_hash(path)
                   for index, root in enumerate(source_roots) for path in sorted(root.rglob('*.java')) if path.is_file()}
        expected = {path.relative_to(staged).as_posix(): file_hash(path)
                    for path in sorted(staged.rglob('*')) if path.is_file()}
        policy_hash = file_hash(policy)
        common_path = Path(settings['_common_config_path']) if settings.get('_common_config_path') else None
        common_hash = file_hash(common_path) if common_path else None
        environment = os.environ.copy()
        if settings.get('java_home'):
            environment['JAVA_HOME'] = settings['java_home']
            environment['PATH'] = str(Path(settings['java_home']) / 'bin') + os.pathsep + environment.get('PATH', '')
        command = [*settings['validator_command'], '--code', str(staged.resolve()), '--policy', str(policy),
                   '--release', str(release)]
        if settings.get('_common_config_path'):
            command += ['--common-config', settings['_common_config_path']]
        # Forward explicit formatter overrides; inherited defaults must not mask validator-local settings.
        explicit_fields = set((config or {}).get('_local_shared_fields', config or {}))
        if 'java_version' in explicit_fields:
            command += ['--java-version', str(settings['java_version'])]
        for key in ('java_home', 'maven_settings_path', 'maven_local_repository'):
            # Empty CLI values explicitly clear a common path overridden with local null.
            if key in explicit_fields:
                command += ['--' + key.replace('_', '-'), settings[key] if settings.get(key) is not None else '']
        for root in source_roots:
            command += ['--support', str(root)]
        announce('Checking policy and compiling generated Java...')
        with WaitProgress('Policy and compilation', settings['validator_timeout_seconds']):
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', timeout=settings['validator_timeout_seconds'], env=environment)
        (attempt / 'validator.stdout.txt').write_text(result.stdout, encoding='utf-8')
        (attempt / 'validator.stderr.txt').write_text(result.stderr, encoding='utf-8')
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or report.get('schema_version') != 'java-policy-validation-v1':
            raise ValueError('Malformed validator report schema')
        write_json(report_path, report)
        status = report.get('status')
        if status not in {'passed', 'failed', 'error'} or result.returncode != {'passed': 0, 'failed': 1, 'error': 2}[status]:
            raise ValueError('Validator status and exit code disagree')
        if status == 'error':
            raise ValueError('Validator error: ' + str(report.get('error', 'no error details')))
        if report.get('files') != expected or report.get('policy_hash') != policy_hash:
            raise ValueError('Validator report does not match the candidate or policy')
        if expected != {path.relative_to(staged).as_posix(): file_hash(path)
                        for path in sorted(staged.rglob('*')) if path.is_file()} or file_hash(policy) != policy_hash:
            raise ValueError('Candidate or policy changed during validation')
        if common_path and file_hash(common_path) != common_hash:
            raise ValueError('Common configuration changed during validation')
        if report.get('input_hash') != hashlib.sha256(json.dumps(expected, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest():
            raise ValueError('Validator omitted its input fingerprint')
        if not isinstance(report.get('findings'), list) or not report.get('tool_version') or not report.get('policy_version'):
            raise ValueError('Validator report is incomplete')
        compilation = report.get('compilation', {})
        if status == 'passed' and (compilation.get('status') != 'passed' or compilation.get('release') != release
                                  or compilation.get('support_files') != support
                                  or 'compilation' not in report.get('checks', [])):
            raise ValueError('Validator did not provide a matching successful compilation check')
        if support != {'support/' + str(index) + '/' + path.relative_to(root).as_posix(): file_hash(path)
                       for index, root in enumerate(source_roots) for path in sorted(root.rglob('*.java')) if path.is_file()}:
            raise ValueError('Support sources changed during validation')
        if status == 'failed' or report['findings']:
            reason = '; '.join(concise(item.get('message', item.get('rule', '')), 160)
                               for item in report['findings'][:2] if isinstance(item, dict))
            raise ValueError('Generated candidate failed policy validation: ' + reason + '; see ' + str(report_path))
        announce('Policy and compilation passed.')
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Preserve genuine findings; infrastructure failures have their own durable receipt.
        write_json(attempt / 'validation-rejection.json', dict(status='rejected', message=str(error)))
        reason = 'Policy and compilation timed out after ' + duration(error.timeout) if isinstance(error, subprocess.TimeoutExpired) else str(error)
        raise ValueError('External validation did not pass: ' + reason) from error
