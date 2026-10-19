"""Replay the latest JUnit/JSON failures without live provider or Maven requests."""

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.response_json import clean_structural_escapes, JSON_INSTRUCTION
from runtime.managed_conversion_response import _remove_response_fence
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier


def responses():
    return json.loads((Path(__file__).parent / 'fixtures/latest_junit_json_responses.json').read_text(encoding='utf-8'))


def test_latest_corrections_parse_without_changing_java_sources():
    original = NativeUnitBundle.model_validate_json(_remove_response_fence(responses()[0]))
    for raw in responses()[1:]:
        with pytest.raises(ValueError):
            NativeUnitBundle.model_validate_json(_remove_response_fence(raw))
        corrected = NativeUnitBundle.model_validate_json(clean_structural_escapes(_remove_response_fence(raw)))
        prefix = _remove_response_fence(raw).split('"dependencies"', 1)[0].rstrip().rstrip(',') + '}'
        assert [item.model_dump() for item in corrected.files] == json.loads(prefix)['files']
        assert corrected.dependencies == original.dependencies


def test_escaped_java_strings_are_untouched_and_other_invalid_json_is_rejected():
    raw = json.dumps({'content': 'String value = "quoted";\nString path = "C:\\tmp";'})
    assert clean_structural_escapes(raw) == raw
    with pytest.raises(json.JSONDecodeError):
        json.loads(clean_structural_escapes('{bad: 1}'))


def test_latest_junit_aggregate_checks_exact_api_artifact(monkeypatch, tmp_path):
    bundle = NativeUnitBundle.model_validate_json(_remove_response_fence(responses()[0]))
    junit = next(item for item in bundle.dependencies if item.artifact_id == 'junit-jupiter')
    for artifact in ('junit-jupiter', 'junit-jupiter-api'):
        path = tmp_path / 'org/junit/jupiter' / artifact / junit.version / f'{artifact}-{junit.version}.jar'
        path.parent.mkdir(parents=True)
        with ZipFile(path, 'w') as jar:
            if artifact.endswith('-api'):
                jar.writestr('org/junit/jupiter/api/Test.class', b'fixture')
    commands = []
    verifier = MavenRepositoryVerifier(None, [], str(tmp_path))
    def run(arguments, directory):
        commands.append(arguments)
        for argument in arguments:
            if argument.startswith('-DoutputFile='):
                Path(argument.split('=', 1)[1]).write_text(json.dumps({'children': [dict(
                    groupId='org.junit.jupiter', artifactId='junit-jupiter', version=junit.version, type='jar',
                    children=[dict(groupId='org.junit.jupiter', artifactId='junit-jupiter-api',
                                   version=junit.version, type='jar', scope='test')])]}), encoding='utf-8')
        return subprocess.CompletedProcess(arguments, 0, '', '')
    monkeypatch.setattr(verifier, '_run', run)
    verifier(junit)
    assert any('org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree' in command for command in commands)
    assert junit.artifact_id == 'junit-jupiter'
    with pytest.raises(ValueError, match='Required API missing'):
        verifier(junit.model_copy(update={'required_classes': ['org.junit.jupiter.api.Nonexistent']}))


def test_correction_instruction_requires_structural_json():
    assert 'dependencies must be an array of objects' in JSON_INSTRUCTION
    assert 'every response (initial or correction)' in JSON_INSTRUCTION
    assert 'valid JSON syntax' in JSON_INSTRUCTION
