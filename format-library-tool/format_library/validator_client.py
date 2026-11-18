"""CLI/JSON boundary to an independent validator; no validator modules are imported."""
import os
import hashlib
from pathlib import Path
import subprocess
from format_library.configuration import DEFAULTS
from format_library.files import file_hash, write_json
import json


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
        environment = os.environ.copy()
        if settings.get('java_home'):
            environment['JAVA_HOME'] = settings['java_home']
            environment['PATH'] = str(Path(settings['java_home']) / 'bin') + os.pathsep + environment.get('PATH', '')
        command = [*settings['validator_command'], '--code', str(staged.resolve()), '--policy', str(policy),
                   '--release', str(release)]
        for root in source_roots:
            command += ['--support', str(root)]
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
            raise ValueError('Generated candidate failed policy validation; see ' + str(report_path))
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Preserve genuine findings; infrastructure failures have their own durable receipt.
        write_json(attempt / 'validation-rejection.json', dict(status='rejected', message=str(error)))
        raise ValueError('External validation did not pass: ' + str(error)) from error
