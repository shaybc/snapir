"""Verify resolved-JAR ownership and replay the latest live JUnit rejection."""

import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest
from models.maven_dependency import MavenDependency
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from tests.runtime.test_behavior_conversion import state, profile
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier


def jar(cache, group, artifact, version, classes):
    path = cache.joinpath(*group.split('.'), artifact, version, f'{artifact}-{version}.jar')
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w') as archive:
        for name in classes:
            archive.writestr(name.replace('.', '/') + '.class', b'fixture')
    return path


def latest_bundle():
    path = Path(__file__).parent / 'runtime/fixtures/latest_junit_engine_response.json'
    return NativeUnitBundle.model_validate_json(path.read_text(encoding='utf-8'))


def mock_resolution(monkeypatch, cache, nodes):
    verifier = MavenRepositoryVerifier('custom-settings.xml', [], str(cache))
    calls = []
    def run(arguments, directory):
        calls.append(arguments)
        for argument in arguments:
            if argument.startswith('-DoutputFile='):
                Path(argument.split('=', 1)[1]).write_text(json.dumps({'children': nodes}), encoding='utf-8')
        return subprocess.CompletedProcess(arguments, 0, '', '')
    monkeypatch.setattr(verifier, '_run', run)
    return verifier, calls


def junit_resolution(monkeypatch, tmp_path):
    bundle = latest_bundle()
    engine = next(item for item in bundle.dependencies if item.artifact_id == 'junit-jupiter-engine')
    jar(tmp_path, engine.group_id, engine.artifact_id, engine.version, ['org.junit.jupiter.engine.JupiterTestEngine'])
    jar(tmp_path, engine.group_id, 'junit-jupiter-api', engine.version, ['org.junit.jupiter.api.Test'])
    nodes = [dict(groupId=engine.group_id, artifactId=engine.artifact_id, version=engine.version,
        type='jar', scope='test', children=[dict(groupId=engine.group_id, artifactId='junit-jupiter-api',
            version=engine.version, type='jar', scope='test')])]
    verifier, calls = mock_resolution(monkeypatch, tmp_path, nodes)
    return bundle, engine, verifier, calls


def test_junit_engine_accepts_verified_transitive_api_without_mutating_metadata(monkeypatch, tmp_path, caplog):
    _, engine, verifier, calls = junit_resolution(monkeypatch, tmp_path)
    with caplog.at_level('DEBUG', logger='tools.maven_dependency_tools.repository_verifier'):
        verifier(engine)
    assert f'{engine.group_id}:junit-jupiter-api:{engine.version}' in caplog.text
    assert 'org.junit.jupiter.api.Test' in caplog.text
    assert all('--settings' in call and f'-Dmaven.repo.local={tmp_path}' in call for call in calls)
    assert engine.required_classes == ['org.junit.jupiter.api.Test']


def test_transitive_classes_do_not_trigger_a_model_correction(monkeypatch, tmp_path):
    bundle, engine, verifier, _ = junit_resolution(monkeypatch, tmp_path)
    conn, config = state()
    requests = []
    def model(instruction, payload):
        requests.append(json.loads(payload))
        return bundle.model_dump_json()
    def validate(output, cached=False):
        for dependency in output.dependencies:
            verifier(dependency)
    result, _ = generate(conn, config, profile(), 'unit', bundle.unit_contract.unit_id,
                         'Convert the step', {}, NativeUnitBundle, validate, model)
    assert len(requests) == 1
    assert result == bundle


def test_non_junit_owner_uses_resolved_version_not_parent_version(monkeypatch, tmp_path):
    dependency = MavenDependency(group_id='org.example', artifact_id='client', version='9.0', reason='Client',
                                 required_classes=['org.example.api.Result'])
    jar(tmp_path, 'org.example', 'client', '9.0', [])
    jar(tmp_path, 'org.example', 'api', '2.4', ['org.example.api.Result'])
    verifier, _ = mock_resolution(monkeypatch, tmp_path, [dict(groupId='org.example', artifactId='client',
        version='9.0', type='jar', children=[dict(groupId='org.example', artifactId='api', version='2.4', type='jar')])])
    verifier(dependency)
    assert dependency.version == '9.0'


def test_latest_response_accepts_junit_aggregate_and_all_source_contracts(monkeypatch, tmp_path):
    from runtime.behavior_conversion.bundle_output import validate_bundle
    fixture = Path(__file__).parent / 'runtime/fixtures/latest_transitive_dependency_response.json'
    bundle = NativeUnitBundle.model_validate_json(fixture.read_text(encoding='utf-8'))
    junit = next(item for item in bundle.dependencies if item.artifact_id == 'junit-jupiter')
    jar(tmp_path, junit.group_id, junit.artifact_id, junit.version, [])
    jar(tmp_path, junit.group_id, 'junit-jupiter-api', junit.version,
        ['org.junit.jupiter.api.Test', 'org.junit.jupiter.api.Assertions'])
    nodes = [dict(groupId=junit.group_id, artifactId=junit.artifact_id, version=junit.version, type='jar', scope='test',
        children=[dict(groupId=junit.group_id, artifactId='junit-jupiter-api', version=junit.version, type='jar', scope='test')])]
    verifier, _ = mock_resolution(monkeypatch, tmp_path, nodes)
    original = bundle.model_dump_json()
    for dependency in bundle.dependencies:
        verifier(dependency)
    assert validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements,
                           bundle.unit_contract.evidence_ids)
    assert bundle.model_dump_json() == original


def test_mixed_found_and_missing_classes_only_report_real_missing_class(monkeypatch, tmp_path):
    _, engine, verifier, _ = junit_resolution(monkeypatch, tmp_path)
    engine.required_classes = ['org.junit.jupiter.api.Test', 'org.junit.jupiter.api.Nonexistent']
    with pytest.raises(ValueError) as caught:
        verifier(engine)
    assert 'org.junit.jupiter.api.Nonexistent' in str(caught.value)
    assert 'org.junit.jupiter.api.Test' not in str(caught.value)


def test_transitive_retry_marker_preserves_accepted_unit_identity():
    from runtime.behavior_conversion.runner import _dependency_validation_version
    from tools.state_store_tools.behavior_units import save
    conn, config = state()
    save(conn, config.run_id, 'unit', 'accepted', 'existing', {})
    save(conn, config.run_id, 'unit', 'failed', 'existing', {}, 'failed', 'Required API missing')
    for identity in ('accepted', 'failed'):
        payload = {}
        _dependency_validation_version(conn, config.run_id, 'unit', identity, payload,
                                       'transitive_class_validation', 'resolved-transitive-api-v1')
        assert ('transitive_class_validation' in payload) == (identity == 'failed')


def test_unrelated_cache_and_missing_classes_are_not_guessed(monkeypatch, tmp_path):
    dependency = MavenDependency(group_id='org.example', artifact_id='client', version='1.0', reason='Client',
                                 required_classes=['org.example.Missing'])
    jar(tmp_path, 'org.example', 'client', '1.0', [])
    jar(tmp_path, 'unrelated', 'cached', '7.0', ['org.example.Missing'])
    verifier, _ = mock_resolution(monkeypatch, tmp_path, [dict(groupId='org.example', artifactId='client', version='1.0', type='jar')])
    with pytest.raises(ValueError, match='No JAR in this resolved dependency graph') as caught:
        verifier(dependency)
    assert 'unrelated' not in str(caught.value)


def test_duplicate_resolved_owners_are_reported_as_ambiguous(monkeypatch, tmp_path):
    dependency = MavenDependency(group_id='org.example', artifact_id='client', version='1.0', reason='Client',
                                 required_classes=['org.example.Result'])
    jar(tmp_path, 'org.example', 'client', '1.0', [])
    children = []
    for artifact in ('api-one', 'api-two'):
        jar(tmp_path, 'org.example', artifact, '1.0', ['org.example.Result'])
        children.append(dict(groupId='org.example', artifactId=artifact, version='1.0', type='jar'))
    verifier, _ = mock_resolution(monkeypatch, tmp_path, [dict(groupId='org.example', artifactId='client', version='1.0', type='jar', children=children)])
    with pytest.raises(ValueError, match='Ownership is ambiguous') as caught:
        verifier(dependency)
    assert 'api-one' in str(caught.value) and 'api-two' in str(caught.value)


def test_unresolved_graph_does_not_invent_class_ownership(monkeypatch, tmp_path):
    dependency = MavenDependency(group_id='org.example', artifact_id='client', version='1.0', reason='Client',
                                 required_classes=['org.example.Result'])
    jar(tmp_path, 'org.example', 'client', '1.0', [])
    verifier = MavenRepositoryVerifier(None, [], str(tmp_path))
    def run(arguments, directory):
        return subprocess.CompletedProcess(arguments, 1 if any(':tree' in item for item in arguments) else 0, '', '')
    monkeypatch.setattr(verifier, '_run', run)
    with pytest.raises(ValueError, match='could not inspect the resolved dependency graph') as caught:
        verifier(dependency)
    assert 'Verified owner' not in str(caught.value)


def test_retry_version_preserves_accepted_task_identity():
    from runtime.behavior_conversion.runner import _dependency_validation_version
    from tools.state_store_tools.behavior_units import save
    conn, config = state()
    save(conn, config.run_id, 'unit', 'already-accepted', 'existing', {'files': []})
    accepted = {}
    _dependency_validation_version(conn, config.run_id, 'unit', 'already-accepted', accepted)
    assert 'dependency_validation' not in accepted
    save(conn, config.run_id, 'unit', 'rejected', 'existing', {}, 'failed', 'Required API missing')
    failed = {}
    _dependency_validation_version(conn, config.run_id, 'unit', 'rejected', failed)
    assert failed['dependency_validation'] == 'resolved-class-ownership-v1'


def test_offline_maven_accepts_and_builds_latest_transitive_response(monkeypatch, tmp_path):
    engine = next(item for item in latest_bundle().dependencies if item.artifact_id == 'junit-jupiter-engine')
    cache = Path.home() / '.m2/repository'
    jdk = Path('C:/Program Files/Java/jdk-25.0.3')
    if not shutil.which('mvn') or not jdk.is_dir() or not (cache / 'org/junit/jupiter/junit-jupiter-api/5.10.2/junit-jupiter-api-5.10.2.jar').is_file():
        pytest.skip('Offline Maven/JDK/JUnit fixture is unavailable')
    verifier = MavenRepositoryVerifier(None, [], str(cache))
    original = verifier._arguments
    monkeypatch.setattr(verifier, '_arguments', lambda: original() + ['--offline'])
    from runtime.java_toolchain import java_scope
    with java_scope(profile(java_version=25, java_home=str(jdk))):
        verifier(engine)
        fixture = Path(__file__).parent / 'runtime/fixtures/latest_transitive_dependency_response.json'
        bundle = NativeUnitBundle.model_validate_json(fixture.read_text(encoding='utf-8'))
        for dependency in bundle.dependencies:
            verifier(dependency)
        from types import SimpleNamespace
        from runtime.behavior_conversion.bundle_output import accept_bundle, validate_bundle
        from runtime.behavior_conversion.ownership import create_native_context
        from tools.maven_dependency_tools.build_context import ManagedBuildContext
        settings = profile(java_version=25, java_home=str(jdk))
        config = SimpleNamespace(run_id='offline-transitive-response')
        def context(settings, project, artifact):
            return create_native_context(config, settings, project,
                lambda settings, project, artifact: ManagedBuildContext(str(project / 'pom.xml'), verifier))
        files = validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements,
                                bundle.unit_contract.evidence_ids)
        result, manifest = accept_bundle(tmp_path / 'latest-response', files, context, settings, bundle.dependencies,
            required_tests={name for paths in bundle.coverage.values() for name in paths})
        assert result['build_passed'] and result['tests_passed'] and result['test_count'] > 0
        assert manifest
