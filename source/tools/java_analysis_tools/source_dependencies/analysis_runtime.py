"""Run the shared JDK analyzer without a second converter-specific AST implementation."""

import atexit
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from runtime.java_toolchain import java_environment

_runtimes = {}


def analyzer_sources():
    """Locate the canonical source module distributed alongside the converter."""
    return Path(__file__).resolve().parents[3] / 'java-analysis-core/src/main/java'


def analyzer_fingerprint():
    """Include the actual shared implementation in content-verified cache keys."""
    digest = hashlib.sha256()
    for path in sorted(analyzer_sources().rglob('*.java')):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def analyzer_command():
    """Compile once per process/toolchain, then reuse bounded batch invocations."""
    environment = java_environment()
    compiler = shutil.which('javac', path=environment.get('PATH') if environment else None)
    if compiler is None:
        raise OSError('Shared Java analyzer requires an available JDK compiler')
    key = (compiler, analyzer_fingerprint())
    if key not in _runtimes:
        temporary = tempfile.TemporaryDirectory(prefix='snapir-java-analysis-core-')
        try:
            result = subprocess.run([compiler, '--release', '21', '-encoding', 'UTF-8', '-d', temporary.name,
                                     *map(str, analyzer_sources().rglob('*.java'))],
                                    capture_output=True, text=True, check=False, env=environment, timeout=120)
            if result.returncode:
                raise OSError('Could not compile shared Java analyzer: ' + result.stderr[-2000:])
        except BaseException:
            temporary.cleanup()
            raise
        _runtimes[key] = temporary
        atexit.register(temporary.cleanup)
    return ['java', '-cp', _runtimes[key].name, 'il.co.dcd.javaanalysis.ReferenceScanMain']
