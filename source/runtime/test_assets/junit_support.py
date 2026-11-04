"""Versioned JUnit fixture helper installation, staging and execution evidence."""
import json
import shutil
import tempfile
from threading import Lock
from pathlib import Path
from models.maven_dependency import MavenDependency
from runtime.test_assets.store import load
from tools.behavior_verification.java_tool import default_tool_path

_installed=set()
_installation=Lock()


def runtime_source_revision():
    """Bind fixture manifests to the exact helper sources and dependency declaration."""
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    from tools.behavior_verification.experimental_checkpoint import file_hash
    root=Path(__file__).resolve().parents[2]/'behavior-verification-java'
    return digest({str(p.relative_to(root)):file_hash(p) for p in [root/'pom.xml',*sorted((root/'src/main/java').rglob('*.java'))]})


def dependency():
    """The helper is test-only; it must never be injected into production sources."""
    return MavenDependency(group_id='il.co.dcd',artifact_id='behavior-verification',version='1.0.0',scope='test',
        reason='Converter-owned immutable fixture runtime',required_classes=[
            'il.co.dcd.verification.fixtures.FixtureStore','il.co.dcd.verification.fixtures.FixtureResult'])


def install_runtime(profile):
    """Build/install the local tool with the existing Maven settings, without publication."""
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    from runtime.java_toolchain import java_environment
    root=Path(__file__).resolve().parents[2]/'behavior-verification-java'
    verifier=MavenRepositoryVerifier(profile.maven_settings_path,profile.approved_maven_repository_urls,profile.maven_local_repository,timeout_seconds=300)
    verifier.environment=java_environment(profile.java_version,profile.java_home)
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    from runtime.dependency_policy import load_policy
    policy=load_policy(profile)
    key=digest(dict(sources=runtime_source_revision(),
        settings=profile.maven_settings_path,repository=profile.maven_local_repository,policy=policy.model_dump(mode='json') if policy else None))
    with _installation:
        if key in _installed:return
        # Installing the test helper must not rewrite the analysis JAR used by an active conversion.
        with tempfile.TemporaryDirectory(prefix='snapir-fixture-runtime-') as folder:
            staged=Path(folder);shutil.copy2(root/'pom.xml',staged/'pom.xml');shutil.copytree(root/'src',staged/'src')
            from tools.maven_dependency_tools.shared_policy_pom import apply_shared_policy
            apply_shared_policy(staged/'pom.xml',profile)
            result=verifier._run(verifier._arguments()+['-DskipTests','install'],staged)
        if result.returncode:raise ValueError('Fixture runtime installation failed: '+(result.stdout+result.stderr)[-3000:])
        _installed.add(key)


def stage(project, assets):
    """Copy a verified immutable revision into the Maven test resources."""
    load(assets['root'],assets['manifest_hash'])
    relative='src/test/resources/shared-test-assets/'+assets['manifest_hash']
    destination=Path(project)/relative
    if destination.exists():load(destination,assets['manifest_hash'])
    else:shutil.copytree(assets['root'],destination)
    return relative


def check_definition(tests, assets):
    """Require explicit test/scenario links and preserve unresolved inputs as blocking tests."""
    if tests.fixture_manifest_hash!=assets['manifest_hash']:raise ValueError('JUnit references a stale fixture manifest')
    suite=assets['junit']
    if suite.unresolved or assets['bank'].unresolved or any(s.unresolved for s in suite.scenarios):raise ValueError('JUnit scenarios have unresolved inputs')
    if set(tests.scenario_methods)!={s.scenario_id for s in suite.scenarios}:raise ValueError('JUnit must implement every declared scenario')
    if len(set(tests.scenario_methods.values()))!=len(tests.scenario_methods):raise ValueError('Each scenario needs a distinct JUnit test method')
    files={f.path.removeprefix('src/test/java/').removesuffix('.java').replace('/','.'):f.content for f in tests.files}
    for identity,method in tests.scenario_methods.items():
        owner,separator,name=method.partition('#')
        if not separator or owner not in files or not name.isidentifier():raise ValueError('Scenario references an unknown JUnit method')
        # Actual helper invocation is proved by runtime receipts, not Java spelling/whitespace.


def invocation_evidence(inventory, assets):
    """Expose declared helper invocations to existing scope guards; receipts must later prove execution."""
    return dict(inventory,calls=[*inventory.get('calls',[]),*[
        dict(receiver_type=s.native_entry.owner_type,method=s.native_entry.method_name,
             origin='fixture_scenario',scenario_id=s.scenario_id,manifest_hash=assets['manifest_hash'])
        for s in assets['junit'].scenarios if s.entry_kind=='method']])


def check_execution(project, tests):
    """A metadata link is not execution: require a passing Surefire testcase for every ID."""
    from xml.etree import ElementTree as ET
    evidence={};observed=set()
    owners={file.path.removeprefix('src/test/java/').removesuffix('.java').replace('/','.') for file in getattr(tests,'files',[])}
    if not owners:owners={method.partition('#')[0] for method in tests.scenario_methods.values()}
    for path in (Path(project)/'target/surefire-reports').glob('TEST-*.xml'):
        for case in ET.parse(path).getroot().iter('testcase'):
            method=case.get('classname')+'#'+case.get('name')
            if any(case.get('classname')==owner or case.get('classname').startswith(owner+'$') for owner in owners):observed.add(method)
            if not any(case.find(tag) is not None for tag in ['failure','error','skipped']):
                evidence[method]=True
    unexpected=observed-set(tests.scenario_methods.values())
    if unexpected:raise ValueError('Generated JUnit methods lack shared-fixture scenario definitions: '+str(sorted(unexpected)))
    missing=[key for key,method in tests.scenario_methods.items() if method not in evidence]
    if missing:raise ValueError('Shared fixture JUnit scenarios did not execute successfully: '+str(missing))
    path=Path(project)/'target/shared-fixture-executions.jsonl'
    records=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []
    missing=[key for key,method in tests.scenario_methods.items() if not any(record.get('scenario_id')==key and
        record.get('manifest_hash')==tests.fixture_manifest_hash and method in record.get('callers',[]) for record in records)]
    if missing:raise ValueError('Passing JUnit methods did not execute their fixture scenarios: '+str(missing))
