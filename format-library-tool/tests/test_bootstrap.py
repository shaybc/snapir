"""Startup checks preserve installed packages and build only stale scanner infrastructure."""
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library import bootstrap, java_prerequisites as java
from format_library.files import file_hash, write_json


def test_satisfied_python_dependencies_do_not_invoke_installer(monkeypatch):
    monkeypatch.setattr(bootstrap, 'unmet_requirements', lambda path: [])
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda *a, **k: pytest.fail('Unneeded installation'))
    bootstrap.ensure_python()


def test_missing_python_dependencies_install_without_upgrade(monkeypatch):
    answers = iter([['missing-package>=1'], []])
    monkeypatch.setattr(bootstrap, 'unmet_requirements', lambda path: next(answers))
    calls = []
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda command, **kwargs: calls.append((command, kwargs)))
    bootstrap.ensure_python()
    command, kwargs = calls[0]
    assert command[:4] == [sys.executable, '-m', 'pip', 'install']
    assert '--upgrade' not in command and '-r' in command and kwargs['check']
    assert len(calls) == 1


def test_requirements_follow_active_transitive_dependencies_only(tmp_path, monkeypatch):
    path = tmp_path / 'requirements.txt'; path.write_text('Parent>=1\n')
    installed = {
        'Parent': SimpleNamespace(version='1.2', requires=['Child>=2', 'OptionalThing; extra == "optional"']),
        'Child': SimpleNamespace(version='1', requires=[]),
    }
    def distribution(name):
        if name not in installed:
            raise bootstrap.importlib.metadata.PackageNotFoundError(name)
        return installed[name]
    monkeypatch.setattr(bootstrap.importlib.metadata, 'distribution', distribution)
    assert bootstrap.unmet_requirements(path) == ['Child>=2']
    installed['Child'].version = '2'
    assert bootstrap.unmet_requirements(path) == []
    installed.pop('Child')
    assert bootstrap.unmet_requirements(path) == ['Child>=2']


@pytest.fixture
def scanner(tmp_path, monkeypatch):
    root = tmp_path / 'scanner'
    (root / 'src').mkdir(parents=True)
    (root / 'pom.xml').write_text('<project/>')
    (root / 'src/Scanner.java').write_text('class Scanner {}')
    jar = root / 'target/scanner.jar'
    monkeypatch.setattr(java, 'SCANNER_ROOT', root)
    monkeypatch.setattr(java, 'SCANNER_JAR', jar)
    monkeypatch.setattr(java, 'BUILD_STATE', root / 'target/build-state.json')
    monkeypatch.setattr(java, 'java_environment', lambda config: ('java', {'PATH': 'jdk-bin'}))
    def archive():
        jar.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(jar, 'w') as output:
            output.writestr(java.MAIN_CLASS, b'class bytes')
    return root, jar, archive


def test_ready_java_scanner_does_not_need_maven(scanner, monkeypatch):
    root, jar, archive = scanner
    archive()
    write_json(java.BUILD_STATE, dict(inputs=java._inputs(), jar=file_hash(jar)))
    monkeypatch.setattr(java.shutil, 'which', lambda *a, **k: pytest.fail('Unneeded Maven lookup'))
    assert java.ensure_scanner({})[0] == 'java'


@pytest.mark.parametrize('change', ['missing', 'source', 'pom', 'jar', 'force'])
def test_missing_or_changed_java_scanner_builds_only_its_project(scanner, monkeypatch, change):
    root, jar, archive = scanner
    if change != 'missing':
        archive()
        write_json(java.BUILD_STATE, dict(inputs=java._inputs(), jar=file_hash(jar)))
    if change in {'source', 'pom'}:
        path = root / ('src/Scanner.java' if change == 'source' else 'pom.xml')
        path.write_text(path.read_text() + ' changed')
    if change == 'jar':
        jar.write_bytes(b'corrupt')
    calls = []
    monkeypatch.setattr(java.shutil, 'which', lambda *a, **k: 'mvn')
    def build(command, environment, timeout, **kwargs):
        calls.append(command)
        archive()
    monkeypatch.setattr(java, 'run_process', build)
    config = dict(java_scan_inactivity_timeout_seconds=120, maven_settings_path='settings.xml',
                  maven_local_repository='local-repository')
    java.ensure_scanner(config, force=change == 'force')
    assert len(calls) == 1 and str(root / 'pom.xml') in calls[0]
    assert '-s' in calls[0] and '-Dmaven.repo.local=local-repository' in calls[0]
    assert java._ready(java._inputs())


def test_bootstrap_uses_selected_config_and_stops_after_install_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(bootstrap, 'ensure_python', lambda: calls.append('python'))
    monkeypatch.setattr('format_library.configuration.load_config', lambda path: dict(path=path))
    monkeypatch.setattr(java, 'ensure_scanner', lambda config: calls.append(config))
    assert bootstrap.main(['--config', 'organization.yaml', 'convert', '--folder', 'component']) == 0
    assert calls == ['python', dict(path='organization.yaml')]
    def fail():
        raise ValueError('install failed')
    monkeypatch.setattr(bootstrap, 'ensure_python', fail)
    assert bootstrap.main([]) == 1 and len(calls) == 2


@pytest.mark.parametrize('startup_exit', [0, 7])
def test_windows_launcher_forwards_arguments_and_stops_on_failure(tmp_path, startup_exit):
    import json
    import os
    import shutil
    import subprocess
    if os.name != 'nt':
        pytest.skip('CMD launcher regression requires Windows')
    root = tmp_path / 'tool with spaces'
    package = root / 'format_library'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    code = ("import json,sys\nfrom pathlib import Path\n"
            "path=Path('events.json')\n"
            "events=json.loads(path.read_text()) if path.exists() else []\n"
            "events.append(dict(stage=STAGE,args=sys.argv[1:]))\n"
            "path.write_text(json.dumps(events))\n")
    (package / 'bootstrap.py').write_text("STAGE='bootstrap'\n" + code + '\nraise SystemExit(' + str(startup_exit) + ')\n')
    (package / '__main__.py').write_text("STAGE='cli'\n" + code)
    shutil.copyfile(bootstrap.TOOL_ROOT / 'run.cmd', root / 'run.cmd')
    environment = os.environ.copy()
    environment['FORMAT_LIBRARY_PYTHON'] = sys.executable
    result = subprocess.run(['cmd', '/d', '/c', 'call', str(root / 'run.cmd'),
        '--config', 'organization config.yaml', 'status'], env=environment, capture_output=True, text=True)
    assert (root / 'events.json').is_file(), result.stdout + result.stderr
    events = json.loads((root / 'events.json').read_text())
    assert result.returncode == startup_exit, result.stdout + result.stderr
    assert [event['stage'] for event in events] == (['bootstrap', 'cli'] if startup_exit == 0 else ['bootstrap'])
    assert all(event['args'] == ['--config', 'organization config.yaml', 'status'] for event in events)
