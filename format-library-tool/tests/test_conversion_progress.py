"""Progress is concise and diagnostic; timeouts, attempts and acceptance remain authoritative."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library import progress, model_client
from format_library.files import read_json
from format_library.planning import build_plan
from format_library.workspaces import prepare
from test_tool import config, evidence, response


def clock(monkeypatch):
    value = SimpleNamespace(now=0)
    monkeypatch.setattr(progress, 'time', SimpleNamespace(monotonic=lambda:value.now))
    return value


def test_wait_notices_are_infrequent_and_do_not_change_inactivity(monkeypatch, capsys):
    timer = clock(monkeypatch)
    idle = SimpleNamespace(seconds=33)
    notice = progress.WaitProgress('Generation model',600,inactivity=lambda:idle.seconds)
    notice.update(); timer.now=119; notice.update()
    assert not capsys.readouterr().out
    timer.now=120; notice.update(); notice.update()
    text = capsys.readouterr().out
    assert text.count('\n') == 1 and '2m 0s' in text
    assert 'without model content 33s' in text and 'inactivity limit 10m 0s' in text
    assert idle.seconds == 33
    timer.now=239; notice.update()
    assert not capsys.readouterr().out
    timer.now=240; notice.update()
    assert capsys.readouterr().out.count('\n') == 1


def test_comparison_notice_includes_current_phase_and_model_call_limit(tmp_path, monkeypatch, capsys):
    timer = clock(monkeypatch)
    snapshot = tmp_path/'progress.json'
    def write(call, timeout):
        snapshot.write_text(json.dumps(dict(schema_version='java-behavior-progress-v1', phase='inventory',
            activity='waiting',model_call=call,model_timeout_seconds=timeout)))
    write(1,600)
    notice = progress.WaitProgress('Behavior comparison',900,snapshot=snapshot)
    notice.update()
    assert 'reviewing behavior with the model' in capsys.readouterr().out
    timer.now=120; notice.update()
    text = capsys.readouterr().out
    assert 'identifying original behavior' in text and 'maximum 15m 0s' in text
    assert 'model call 1: waiting 2m 0s of maximum 10m 0s' in text
    timer.now=121; write(2,300); notice.update()
    assert not capsys.readouterr().out
    timer.now=240; notice.update()
    assert 'model call 2: waiting 1m 59s of maximum 5m 0s' in capsys.readouterr().out


@pytest.mark.parametrize('value', ['not JSON','[]','{"schema_version":"wrong"}',
    '{"schema_version":"java-behavior-progress-v1","phase":[],"activity":"waiting"}'])
def test_unavailable_or_invalid_progress_never_controls_the_result(tmp_path, monkeypatch, capsys, value):
    timer = clock(monkeypatch)
    path = tmp_path/'progress.json';path.write_text(value)
    notice = progress.WaitProgress('Behavior comparison',600,snapshot=path)
    timer.now=120;notice.update()
    assert 'still active' in capsys.readouterr().out


def test_wait_observer_stops_when_the_operation_raises(capsys):
    notice = progress.WaitProgress('Validation',600)
    with pytest.raises(ValueError):
        with notice:
            assert notice.thread.is_alive()
            raise ValueError('Rejected')
    assert not notice.thread.is_alive()
    notice.last_notice = -100000
    notice.update()
    assert not capsys.readouterr().out


def test_success_progress_covers_the_pipeline_and_final_folder(config, monkeypatch, capsys):
    folder = prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    monkeypatch.setattr(model_client,'receive',lambda *args:response(read_json(folder/'component.json')))
    destination = model_client.convert(config,folder)
    text = capsys.readouterr().out
    stages = ['Preparing conversion request','sending conversion request','Received model response',
              'Checking policy and compiling','Policy and compilation passed','Preparing original and generated',
              'Comparing behavior','Behavior comparison passed','finished: success']
    positions = [text.index(stage) for stage in stages]
    assert positions == sorted(positions)
    assert str(destination) in text and len(text.splitlines()) <= 10


@pytest.mark.parametrize('failure', ['blocked','policy','comparison'])
def test_failed_attempt_prints_a_reason_and_the_details_folder(config,monkeypatch,capsys,failure):
    folder = prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    payload = json.loads(response(read_json(folder/'component.json')))
    if failure == 'blocked':
        payload = dict(status='blocked',reasons=['Missing required superclass source'])
    elif failure == 'policy':
        payload['files'][0]['content'] += '\nclass Invalid { int value(){return "wrong";} }'
    else:
        Path(config['comparison_config_path']).write_text('{"decision":"differences_found"}')
    monkeypatch.setattr(model_client,'receive',lambda *args:json.dumps(payload))
    if failure == 'blocked':
        assert model_client.convert(config,folder) is None
    else:
        with pytest.raises(ValueError): model_client.convert(config,folder)
    text = capsys.readouterr().out
    expected = {'blocked':'Missing required superclass source','policy':'policy validation','comparison':'Synthetic difference'}
    assert 'Attempt 1/' in text and 'finished:' in text and expected[failure] in text
    assert 'Details' in text and str(folder/'attempts') in text
    assert not (folder/'latest.json').exists()
