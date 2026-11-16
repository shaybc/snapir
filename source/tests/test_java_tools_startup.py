"""Verify both launchers require Java tools without remapping or starting conversion."""

from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from runtime import java_tools_startup as startup


@pytest.fixture
def project(tmp_path, monkeypatch):
    mapper = tmp_path / startup.constants.COMPOSER_MAPPER_JAR
    analyzer = tmp_path / 'source/behavior-verification-java/target/behavior-verification-1.0.0-jar-with-dependencies.jar'
    for name in ('composer-mapper', 'behavior-verification-java'):
        pom = tmp_path / 'source' / name / 'pom.xml'
        pom.parent.mkdir(parents=True)
        pom.write_text('<project><build><release>25</release></build></project>')
    monkeypatch.setattr(startup, 'maven_executable', lambda: 'mvn.cmd')
    monkeypatch.setattr(startup, 'java_environment', lambda version: {'JAVA_HOME': 'jdk-' + str(version)})
    return tmp_path, mapper, analyzer


def jar(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w') as archive:
        archive.writestr(startup.ANALYZER_CAPABILITY, b'existing-tool')
        archive.writestr(startup.ANALYZER_PROGRESS_CAPABILITY, b'existing-tool')


def test_existing_tools_need_no_jdk_lookup_or_maven(project, monkeypatch):
    root, mapper, analyzer = project
    jar(mapper)
    jar(analyzer)
    monkeypatch.setattr(startup, 'java_environment', lambda *args: pytest.fail('Unneeded JDK lookup'))
    monkeypatch.setattr(startup.subprocess, 'run', lambda *args, **kwargs: pytest.fail('Unneeded build'))
    startup.ensure_java_tools(root)


@pytest.mark.parametrize('missing', ['mapper', 'analyzer', 'both'])
def test_only_missing_tools_are_built_and_verified(project, monkeypatch, missing):
    root, mapper, analyzer = project
    if missing == 'mapper': jar(analyzer)
    if missing == 'analyzer': jar(mapper)
    calls = []
    def build(command, **kwargs):
        calls.append(command)
        assert kwargs['cwd'] == root and kwargs['env']['JAVA_HOME'] == 'jdk-25'
        assert command[0] == 'mvn.cmd' and command[-1] == 'package'
        if '-am' in command:
            assert command[command.index('-pl') + 1] == 'composer-mapper'
            jar(mapper)
        else:
            assert 'behavior-verification-java' in command[command.index('-f') + 1]
            jar(analyzer)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(startup.subprocess, 'run', build)
    startup.ensure_java_tools(root)
    assert len(calls) == (2 if missing == 'both' else 1)
    assert mapper.is_file() and analyzer.is_file()


@pytest.mark.parametrize('result', ['failed', 'no-output', 'missing-maven'])
def test_failed_or_incomplete_build_stops_startup(project, monkeypatch, result):
    root, _, analyzer = project
    jar(analyzer)
    def build(*args, **kwargs):
        if result == 'missing-maven':
            raise FileNotFoundError('Maven is missing')
        return SimpleNamespace(returncode=1 if result == 'failed' else 0)
    monkeypatch.setattr(startup.subprocess, 'run', build)
    with pytest.raises((ValueError, OSError)):
        startup.ensure_java_tools(root)


def test_launchers_share_the_check_before_cli_and_stop_on_failure():
    root = Path(__file__).resolve().parents[2]
    normal = (root / 'run.cmd').read_text()
    verbose = (root / 'run-verbose.cmd').read_text()
    assert normal.index('-m runtime.java_tools_startup') < normal.index('-m cli')
    guard = normal[normal.index('-m runtime.java_tools_startup'):normal.index('-m cli')]
    assert 'goto finish' in guard and 'pause' in guard
    assert 'run.cmd" --verbose %*' in verbose


@pytest.mark.parametrize('capability', ['old-analyzer.class', startup.ANALYZER_CAPABILITY])
def test_existing_old_analyzer_is_rebuilt_before_launch(project, monkeypatch, capability):
    root, mapper, analyzer = project
    jar(mapper)
    analyzer.parent.mkdir(parents=True)
    with ZipFile(analyzer, 'w') as archive:
        archive.writestr(capability, b'old')
    calls = []
    def build(command, **kwargs):
        calls.append(command)
        assert 'behavior-verification-java' in command[command.index('-f') + 1]
        jar(analyzer)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(startup.subprocess, 'run', build)
    startup.ensure_java_tools(root)
    assert len(calls) == 1
