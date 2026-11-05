"""Build a content-bound shared runtime using the converter's managed dependency checks."""
import hashlib
import json
import shutil
from pathlib import Path
from models.maven_dependency import MavenDependency
from runtime.managed_projects import create_build_context


def runtime_sources():
    """Return the maintained library sources supplied to wrapper generation as API context."""
    return Path(__file__).resolve().parents[2] / 'integration-runtime-java'


def runtime_fingerprint():
    root = runtime_sources()
    digest = hashlib.sha256()
    for path in sorted([root/'pom.xml', *root.joinpath('src').rglob('*')]):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def install_runtime(profile, directory):
    """Test/package/install only a copied library tree, keeping its source project immutable."""
    fingerprint = runtime_fingerprint()
    project = Path(directory)/'shared-runtime'/fingerprint[:16]
    if not project.exists():
        shutil.copytree(runtime_sources(), project, ignore=shutil.ignore_patterns('target'))
    context = create_build_context(profile, project, 'native-integration-runtime')
    result = context.verifier.compile_project(project, context.allowed_ibm_artifacts, goal='install')
    (project/'build.log').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('Shared integration runtime build failed: ' + result.stdout[-4000:] + result.stderr[-1500:])
    dependency = MavenDependency(group_id='il.co.dcd', artifact_id='native-integration-runtime',version='1.0.0',
        reason='Shared named pools and transaction-aware native operation runtime',
        required_classes=['il.co.dcd.integration.DatabaseExecution','il.co.dcd.integration.NativeRuntimeConfiguration'])
    return dependency, dict(fingerprint=fingerprint, project=str(project), build_passed=True,
        jar_hash=hashlib.sha256((project/'target/native-integration-runtime-1.0.0.jar').read_bytes()).hexdigest())
