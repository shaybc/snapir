"""Independent launcher with common Java configuration; reports use stdout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import importlib.util

ROOT = Path(__file__).resolve().parent
JAR = ROOT / 'target/java-policy-validator-1.0.0-jar-with-dependencies.jar'


def main():
    """Build this validator when necessary, then forward its JSON result and exit code."""
    class JsonArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)
    parser = JsonArgumentParser()
    parser.add_argument('--code', required=True)
    parser.add_argument('--config', default=str(ROOT / 'config.yaml'), help='Validator-local overrides of common defaults')
    parser.add_argument('--policy', default=str(ROOT / 'policy.json'))
    parser.add_argument('--common-config', help='Converter YAML containing shared Java and Maven settings')
    parser.add_argument('--support', action='append', default=[], help='Native Java support source directory (repeatable)')
    parser.add_argument('--release', type=int, help='Explicit compile target; otherwise local target_java_version or effective java_version')
    parser.add_argument('--java-home', help='Explicit JDK home override')
    parser.add_argument('--java-version', type=int, help='Explicit JDK major version override')
    parser.add_argument('--maven-settings-path', help='Explicit Maven settings file override')
    parser.add_argument('--maven-local-repository', help='Explicit Maven repository override')
    try:
        args = parser.parse_args()
        if importlib.util.find_spec('yaml') is None:
            installed = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')],
                                       stdout=sys.stderr, stderr=sys.stderr)
            if installed.returncode:
                raise ValueError('Validator YAML requirement installation failed; see stderr')
        from configuration import load
        from java_environment import select_java, maven_options
        overrides = {key: getattr(args, key) for key in ('java_home', 'java_version', 'maven_settings_path', 'maven_local_repository')
                     if getattr(args, key) is not None}
        for key in ('java_home', 'maven_settings_path', 'maven_local_repository'):
            if overrides.get(key) == '':
                overrides[key] = None
        if args.release is not None:
            overrides['target_java_version'] = args.release
        settings = load(args.config, args.common_config, overrides=overrides)
        java, environment = select_java(settings)
        inputs = [ROOT / 'pom.xml', *sorted((ROOT / 'src').rglob('*.java'))]
        revision = hashlib.sha256(b''.join(path.read_bytes() for path in inputs)).hexdigest()
        state = ROOT / 'target/launcher-build.json'
        previous = json.loads(state.read_text()) if state.is_file() else {}
        if not JAR.is_file() or previous != dict(inputs=revision, jar=hashlib.sha256(JAR.read_bytes()).hexdigest()):
            maven = shutil.which('mvn', path=environment['PATH']) or shutil.which('mvn.cmd', path=environment['PATH'])
            if not maven:
                raise ValueError('Maven is required to build the independent validator')
            build = subprocess.run([maven, '-B', '-f', str(ROOT / 'pom.xml'), *maven_options(settings), 'package'],
                                   env=environment, stdout=sys.stderr, stderr=sys.stderr, timeout=600)
            if build.returncode:
                raise ValueError('Validator build failed; see stderr')
            state.write_text(json.dumps(dict(inputs=revision, jar=hashlib.sha256(JAR.read_bytes()).hexdigest())))
        context = dict(source_roots=[str(Path(path).resolve()) for path in args.support])
        context['release'] = settings['target_java_version']
        with tempfile.TemporaryDirectory(prefix='java-policy-inputs-') as temporary:
            inputs_path = Path(temporary) / 'compilation.json'
            inputs_path.write_text(json.dumps(context), encoding='utf-8')
            result = subprocess.run([java, '-jar', str(JAR), str(Path(args.code).resolve()),
                                     str(Path(args.policy).resolve()), str(inputs_path)], env=environment, timeout=600)
        return result.returncode
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        print(json.dumps(dict(schema_version='java-policy-validation-v1', tool_version='1.1.0',
                              status='error', findings=[], error=str(error))))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
