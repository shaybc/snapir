"""Explicit maintenance build; normal release lookup/staging never imports or invokes it."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree
from runtime.fixture_jdbc_tools.releases import canonical, digest, file_hash, default_store
from runtime.fixture_jdbc_tools.artifact_checks import check_packaging


def sources():
    """Locate maintained converter sources, never generated operation projects."""
    return Path(__file__).resolve().parents[2]


def source_files():
    """Include the shared engine and unchanged registry sources used by acceptance tests."""
    root = sources()
    files = [p for p in (root / 'jdbc-fixture-java').rglob('*') if p.is_file() and 'target' not in p.parts]
    files += list((root / 'behavior-verification-java/src').rglob('*.java'))
    files.append(root / 'behavior-verification-java/pom.xml')
    files += list((root / 'integration-runtime-java/src/main/java').rglob('*.java'))
    files += [root / 'tests/test_fixture_jdbc_tools.py', root / 'tests/test_fixture_jdbc_asset_compatibility.py']
    files += [root / 'tests/fixture_jdbc_support.py', root / 'fixture_jdbc_tools.py',
        root / 'models/fixture_jdbc_tool_release.py', root / 'models/fixture_demo_catalogue.py']
    files += list((root / 'runtime/fixture_jdbc_tools').glob('*.py'))
    # Acceptance runs copied converter code, not a live checkout that can change mid-build.
    files += [p for p in root.rglob('*.py') if 'target' not in p.parts and '__pycache__' not in p.parts]
    return sorted(set(files))


def build_release(version, *, store=None, work=None, java_home=None, maven_settings=None, maven_repository=None):
    """Build/test copied sources, package evidence, then explicitly install one immutable release."""
    from runtime.fixture_jdbc_tools.publication import publish_release
    from runtime.java_toolchain import java_environment
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    from tools.maven_dependency_tools.policy import validate_dependency_policy
    from models.maven_dependency import MavenDependency
    root = sources()
    maintained_version = ElementTree.parse(root / 'jdbc-fixture-java/pom.xml').getroot().find('{*}version').text
    if version != maintained_version:
        raise ValueError('Release version must match the maintained Maven reactor')
    files = source_files()
    fingerprint = digest({p.relative_to(root).as_posix(): file_hash(p) for p in files})
    directory = Path(work or root.parent / 'outputs/fixture-jdbc-tool-builds') / fingerprint
    if directory.exists():
        raise ValueError('Build workspace already exists; select a fresh --work directory')
    copied = directory / 'source'
    for path in files:
        target = copied / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    java_environment_values = java_environment(25, java_home)
    verifier = MavenRepositoryVerifier(maven_settings, [], maven_repository, timeout_seconds=600)
    verifier.environment = java_environment_values

    def maven(project, arguments, log):
        result = verifier._run(verifier._arguments() + arguments, project)
        from runtime.model_execution.error_details import sanitize_diagnostic
        (directory / log).write_text(sanitize_diagnostic((result.stdout or '') + '\n' + (result.stderr or '')), encoding='utf-8')
        if result.returncode:
            raise ValueError('Fixture tool build/check failed; inspect ' + str(directory / log))

    project = copied / 'jdbc-fixture-java'
    maven(project, ['clean', 'verify'], 'maven.log')
    maven(project, ['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree', '-DoutputType=json', '-DoutputFile=target/dependency-tree.json'], 'dependencies.log')
    dependencies = []

    def inspect(node):
        if node['groupId'] != 'il.co.dcd':
            dependency = MavenDependency(group_id=node['groupId'], artifact_id=node['artifactId'], version=node['version'], scope=node.get('scope', 'compile'), reason='Pinned converter fixture tool dependency')
            validate_dependency_policy(dependency)
            dependencies.append(dependency.model_dump(mode='json'))
        for child in node.get('children', []):
            inspect(child)

    for tree in project.glob('*/target/dependency-tree.json'):
        inspect(json.loads(tree.read_text(encoding='utf-8')))
    # Build a copy of the original facade; do not overwrite the analysis JAR of a saved run.
    maven(copied / 'behavior-verification-java', ['package'], 'harness.log')
    driver = project / 'fixture-driver/target/fixture-jdbc-driver-1.0.0-standalone.jar'
    server = project / 'fixture-server/target/fixture-server-1.0.0-standalone.jar'
    check_packaging(driver, server)
    environment = dict(java_environment_values)
    environment['PYTHONPATH'] = str(copied) + os.pathsep + str(copied / 'tests')
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['FIXTURE_JDBC_TEST_SOURCE'] = str(copied)
    environment['FIXTURE_JDBC_TEST_JAVA'] = str(Path(java_environment_values['JAVA_HOME']) / 'bin/java.exe' if os.name == 'nt' else Path(java_environment_values['JAVA_HOME']) / 'bin/java')
    tests = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        str(copied / 'tests/test_fixture_jdbc_tools.py'), str(copied / 'tests/test_fixture_jdbc_asset_compatibility.py'),
        '--basetemp', str(directory / 'python-temporary'), '--junitxml', str(directory / 'python-tests.xml')],
        cwd=root.parent, env=environment, text=True, capture_output=True, timeout=600)
    (directory / 'python-tests.log').write_text(tests.stdout + '\n' + tests.stderr, encoding='utf-8')
    if tests.returncode:
        raise ValueError('Fixture tool acceptance failed; inspect ' + str(directory / 'python-tests.log'))
    python_suites = ElementTree.parse(directory / 'python-tests.xml').getroot().findall('testsuite')
    python_count = sum(int(s.get('tests', 0)) for s in python_suites)
    if not python_count or any(int(s.get(k, 0)) for s in python_suites for k in ('errors', 'failures', 'skipped')):
        raise ValueError('Fixture Python acceptance evidence is incomplete')
    java_tests = []
    for path in project.glob('*/target/surefire-reports/TEST-*.xml'):
        suite = ElementTree.parse(path).getroot()
        if int(suite.get('failures', 0)) or int(suite.get('errors', 0)) or int(suite.get('skipped', 0)):
            raise ValueError('Fixture Java tests did not all pass')
        java_tests.append(dict(name=suite.get('name'), tests=int(suite.get('tests', 0)), sha256=file_hash(path)))
    if not java_tests:
        raise ValueError('Fixture Java acceptance evidence missing')
    prepared = directory / 'distribution'
    for src, name in [(driver, 'jdbc/fixture-jdbc-driver.jar'), (server, 'server/fixture-server.jar'),
        (project / 'distribution/fixture-server.bat', 'bin/fixture-server.bat'), (project / 'distribution/fixture-server.sh', 'bin/fixture-server.sh')]:
        target = prepared / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        if name.endswith('.sh'):
            target.chmod(0o755)
    capabilities = subprocess.run([environment['FIXTURE_JDBC_TEST_JAVA'], '-jar', str(server), 'capabilities'],
        capture_output=True, text=True, check=True, timeout=15)
    evidence = prepared / 'evidence'
    evidence.mkdir()
    shutil.copyfile(directory / 'python-tests.xml', evidence / 'python-tests.xml')
    (evidence / 'capabilities.json').write_bytes(canonical(json.loads(capabilities.stdout)))
    receipt = dict(source_fingerprint=fingerprint, java_version=25, java_tests=java_tests,
        python_tests_sha256=file_hash(directory / 'python-tests.xml'), python_tests_passed=python_count, dependencies=dependencies,
        driver_sha256=file_hash(driver), server_sha256=file_hash(server), build_passed=True,
        conversion_resumed=False, model_calls=0)
    (evidence / 'build-receipt.json').write_bytes(canonical(receipt))
    if fingerprint != digest({p.relative_to(root).as_posix(): file_hash(p) for p in source_files()}):
        raise ValueError('Maintained tool sources changed during build; run a fresh explicit build')
    return dict(publish_release(prepared, version, fingerprint, store or default_store()), build_directory=str(directory))
