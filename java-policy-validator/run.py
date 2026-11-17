"""Independent standard-library launcher; build logs use stderr and reports use stdout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
JAR = ROOT / 'target/java-policy-validator-1.0.0-jar-with-dependencies.jar'


def main():
    """Build this validator when necessary, then forward its JSON result and exit code."""
    class JsonArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)
    parser = JsonArgumentParser()
    parser.add_argument('--code', required=True)
    parser.add_argument('--policy', default=str(ROOT / 'policy.json'))
    try:
        args = parser.parse_args()
        java = shutil.which('java')
        if not java:
            raise ValueError('Java 17 or later is required on PATH')
        inputs = [ROOT / 'pom.xml', *sorted((ROOT / 'src').rglob('*.java'))]
        revision = hashlib.sha256(b''.join(path.read_bytes() for path in inputs)).hexdigest()
        state = ROOT / 'target/launcher-build.json'
        previous = json.loads(state.read_text()) if state.is_file() else {}
        if not JAR.is_file() or previous != dict(inputs=revision, jar=hashlib.sha256(JAR.read_bytes()).hexdigest()):
            maven = shutil.which('mvn') or shutil.which('mvn.cmd')
            if not maven:
                raise ValueError('Maven is required to build the independent validator')
            build = subprocess.run([maven, '-B', '-f', str(ROOT / 'pom.xml'), 'package'],
                                   stdout=sys.stderr, stderr=sys.stderr, timeout=600)
            if build.returncode:
                raise ValueError('Validator build failed; see stderr')
            state.write_text(json.dumps(dict(inputs=revision, jar=hashlib.sha256(JAR.read_bytes()).hexdigest())))
        result = subprocess.run([java, '-jar', str(JAR), str(Path(args.code).resolve()),
                                 str(Path(args.policy).resolve())], timeout=600)
        return result.returncode
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        print(json.dumps(dict(schema_version='java-policy-validation-v1', tool_version='1.0.0',
                              status='error', findings=[], error=str(error))))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
