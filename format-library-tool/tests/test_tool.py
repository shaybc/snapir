"""Tool regressions use synthetic source and fake AI responses, never production executions."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration_fixture import write_config
from format_library.configuration import load_config, TOOL_ROOT
from format_library.files import digest, file_hash, read_json, write_json
from format_library.planning import build_plan
from format_library.workspaces import prepare
from format_library.generated_files import extract
from format_library.prompts import build_request
from format_library.approval import approve


@pytest.fixture
def config(tmp_path, monkeypatch):
    source = tmp_path / 'original'; source.mkdir()
    comparison = tmp_path / 'comparison-config.json'
    comparison.write_text('{}')
    path = tmp_path / 'config.yaml'
    write_config(path, dict(source_root=str(source), output_root=str(tmp_path / 'work'),
        approved_library_root=str(tmp_path / 'approved'), native_package='example.nativeformats',
        model_provider='litellm', model_name='openai/fake', model_base_url='http://localhost/v1',
        model_api_key_environment='FORMAT_LIBRARY_TEST_KEY',
        comparison_command=[sys.executable,str(Path(__file__).with_name('fake_comparator_cli.py'))],
        comparison_config_path=str(comparison)))
    monkeypatch.setenv('FORMAT_LIBRARY_TEST_KEY', 'fake-key-never-sent')
    return load_config(path)


def evidence(config, definitions):
    root = Path(config['source_root'])
    classes, hashes = {}, {}
    for name, dependencies in definitions.items():
        path = root / (name.replace('.', '/') + '.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('package example; public class ' + name.rsplit('.', 1)[-1] + ' {}')
        hashes[str(path)] = file_hash(path)
        classes[name] = dict(name=name, kind='format', abstract=False, framework=False,
            file=str(path), project='project', issues=[], dependencies=dependencies)
    return dict(classes=classes, hashes=hashes, issues=[], projects=[dict(id='project', libraries=[], issues=[])])


def response(manifest):
    return json.dumps(dict(status='generated', files=[dict(
        path='src/main/java/' + name.replace('.', '/') + '.java',
        content='package ' + name.rsplit('.', 1)[0] + '; public class ' + name.rsplit('.', 1)[1] + ' {}')
        for name in manifest['native_classes'].values()], components=[dict(original_class=original,
        native_class=native, constructors=['public ' + native.rsplit('.', 1)[1] + '(java.util.Map<String,String> attributes)'])
        for original, native in manifest['native_classes'].items()], dependencies=[], notes=[]))


def generate(config, folder):
    manifest = read_json(folder / 'component.json')
    request = build_request(config, folder, manifest)
    attempt = folder / 'attempts/test'
    attempt.mkdir()
    return extract(folder, manifest, response(manifest), request, attempt, config=config)


def test_cycle_groups_and_dependency_order(config):
    plan = build_plan(evidence(config, {'example.A': ['example.B'], 'example.B': ['example.A'], 'example.Wrapper': ['example.A']}))
    assert plan['groups'][0]['members'] == ['example.A', 'example.B']
    assert plan['groups'][1]['dependencies'] == [plan['groups'][0]['id']]
    folders = prepare(config, plan, ['Wrapper'])
    assert len(folders) == 2
    assert 'A+B' in folders[0].name
    assert (folders[0] / 'prompt.txt').is_file()
    assert (folders[0] / 'common-api/src/main/java/com/snapir/format/api/NativeFormat.java').is_file()
    assert (folders[0] / 'convert.cmd').is_file()


def test_approval_gate_refresh_and_reuse(config):
    folders = prepare(config, build_plan(evidence(config, {'example.Basic': [], 'example.Wrapper': ['example.Basic']})))
    basic, wrapper = folders
    with pytest.raises(ValueError, match='human approval'):
        build_request(config, wrapper, read_json(wrapper / 'component.json'))
    candidate = generate(config, basic)
    with pytest.raises(ValueError, match='--reviewed'):
        approve(config, basic)
    artifact = approve(config, basic, reviewed=True)
    assert artifact.is_dir()
    request = build_request(config, wrapper, read_json(wrapper / 'component.json'))
    assert request['prerequisites']
    assert any(path.startswith('prerequisites/') and path.endswith('.java') for path in request['attachments'])
    assert not any(path.endswith('.jar') for path in request['attachments'])
    # A new review records edited bytes without changing the old approved copy.
    java = next(candidate.rglob('*.java'))
    java.write_text(java.read_text() + '\n// human correction')
    newer = approve(config, basic, reviewed=True)
    assert newer != artifact and artifact.is_dir()
    generate(config, wrapper)
    assert read_json(wrapper / 'latest.json')['candidate'].startswith('generated/')


@pytest.mark.parametrize('path', ['../outside.java', 'src/main/java/../../outside.java',
    'src/test/java/Test.java', 'run.cmd', '/tmp/Bad.java', 'C:/Bad.java', 'src/main/resources/evil.ps1'])
def test_reject_generated_paths(config, path):
    folder = prepare(config, build_plan(evidence(config, {'example.Basic': []})))[0]
    manifest = read_json(folder / 'component.json')
    payload = json.loads(response(manifest))
    payload['files'][0]['path'] = path
    with pytest.raises(ValueError):
        extract(folder, manifest, json.dumps(payload), dict(prerequisites=[]), folder / 'attempts/test')
    assert not (folder / 'latest.json').exists()


def test_evidence_edits_and_size_limit_block_before_model(config):
    folder = prepare(config, build_plan(evidence(config, {'example.Basic': []})))[0]
    manifest = read_json(folder / 'component.json')
    config['request_character_limit'] = 10
    with pytest.raises(ValueError, match='nothing was sent'):
        build_request(config, folder, manifest)
    path = folder / manifest['files'][0]['path']
    path.write_text('edited')
    with pytest.raises(ValueError, match='evidence changed'):
        build_request(config, folder, manifest)


def test_no_overwrite_and_blocked_candidate(config):
    plan = build_plan(evidence(config, {'example.Basic': []}))
    folder = prepare(config, plan)[0]
    (folder / 'generated/human.txt').write_text('keep')
    assert prepare(config, plan)[0] == folder
    assert (folder / 'generated/human.txt').read_text() == 'keep'
    attempt = folder / 'attempts/blocked'; attempt.mkdir()
    result = extract(folder, read_json(folder / 'component.json'),
        '{"status":"blocked","reasons":["need inherited source"]}', dict(prerequisites=[]), attempt)
    assert result is None and read_json(attempt / 'result.json')['status'] == 'blocked'


def test_delivery_failures_retry_without_correction(config, monkeypatch):
    from format_library import model_client
    folder = prepare(config, build_plan(evidence(config, {'example.Basic': []})))[0]
    calls = []
    def receive(settings, path):
        calls.append(read_json(path))
        if len(calls) == 1:
            raise ValueError('No model message delivered: HTML upstream response')
        return response(read_json(folder / 'component.json'))
    monkeypatch.setattr(model_client, 'receive', receive)
    assert model_client.convert(config, folder).is_dir()
    assert calls[0] == calls[1]
    records = [read_json(path) for path in (folder / 'attempts').glob('*/result.json')]
    assert {item['status'] for item in records} == {'delivery_failed', 'generated'}
    assert model_client.delivery_failure('<!DOCTYPE html><html>upstream</html>')
    assert not model_client.delivery_failure('{"status":"blocked"}')


def test_eclipse_classpaths_and_missing_container(config):
    from format_library.classpaths import inventory
    root = Path(config['source_root'])
    (root / 'src').mkdir()
    (root / 'src/Basic.java').write_text('class Basic {}')
    (root / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/>'
        '<classpathentry kind="con" path="vendor.libs"/></classpath>')
    project = inventory(config)['projects'][0]
    assert project['roots'] == [str(root / 'src')]
    assert 'Unresolved Eclipse container' in project['issues'][0]


def test_cli_status_does_not_discover_or_call_ai(config, monkeypatch):
    from format_library.__main__ import main
    monkeypatch.setattr('format_library.discovery.scan', lambda *a, **k: pytest.fail('Unexpected scan'))
    assert main(['--config', config['_config_path'], 'status']) == 0


def test_api_worker_heartbeats_do_not_extend_inactivity(config, monkeypatch, tmp_path):
    from format_library import model_client
    class Clock:
        now = 0
        def tick(self):
            self.now += 2
            return self.now
    clock = Clock()
    config['model_timeout_seconds'] = 1
    class Process:
        stdout = iter(['{"heartbeat":true}\n'] * 10)
        killed = False
        def poll(self): return None
        def kill(self): self.killed = True
        def wait(self): return 0
    class Stream:
        def __iter__(self): return iter(['{"heartbeat":true}\n'] * 10)
        def close(self): pass
    process = Process(); process.stdout = Stream()
    monkeypatch.setattr(model_client.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(model_client.time, 'monotonic', clock.tick)
    with pytest.raises(ValueError, match='heartbeat'):
        model_client.receive(config, tmp_path / 'request.json')
    assert process.killed


def test_api_worker_records_real_content_without_running_provider(config, monkeypatch, tmp_path):
    from format_library import model_client
    class Stream:
        def __iter__(self):
            return iter(['{"delta":"{\\"status\\":\\"blocked\\"}"}\n', '{"done":true}\n'])
        def close(self): pass
    class Process:
        stdout = Stream()
        def poll(self): return 0
        def wait(self): return 0
    monkeypatch.setattr(model_client.subprocess, 'Popen', lambda *a, **k: Process())
    assert model_client.receive(config, tmp_path / 'request.json') == '{"status":"blocked"}'
    assert (tmp_path / 'response.partial.txt').read_text() == '{"status":"blocked"}'


def test_edited_approval_and_manifest_cannot_be_reused(config):
    from format_library.prompts import build_request
    plan = build_plan(evidence(config, {'example.Basic': [], 'example.Wrapper': ['example.Basic']}))
    basic, wrapper = prepare(config, plan)
    generate(config, basic)
    artifact = approve(config, basic, reviewed=True)
    exported = next(artifact.rglob('*.java'))
    exported.write_text('tampered')
    with pytest.raises(ValueError, match='Approved component file changed'):
        build_request(config, wrapper, read_json(wrapper / 'component.json'))
    record = read_json(basic / 'component.json')
    record['blockers'] = ['changed']
    write_json(basic / 'component.json', record)
    with pytest.raises(ValueError, match='record changed'):
        build_request(config, basic, record)


@pytest.mark.parametrize('streaming', [False, True])
def test_litellm_provider_modes_do_not_require_live_api(config, monkeypatch, capsys, streaming):
    from format_library.model_client import worker
    config['model_stream'] = streaming
    def completion(**kwargs):
        assert kwargs['stream'] is streaming
        value = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content='{"status":"blocked"}'))])
        return [value] if streaming else SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"status":"blocked"}'))])
    monkeypatch.setitem(sys.modules, 'litellm', SimpleNamespace(completion=completion))
    worker(config, dict(prompt='instructions', attachments={}, targets={}))
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events == [dict(delta='{"status":"blocked"}'), dict(done=True)]
