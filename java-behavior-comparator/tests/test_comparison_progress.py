"""Optional status snapshots never replace the standalone comparator's canonical JSON report."""
import json
import pytest
from comparator import progress


def test_snapshot_contains_only_diagnostic_stage_and_wait_limits(tmp_path,monkeypatch):
    target = tmp_path/'progress.json'
    monkeypatch.setenv(progress.ENVIRONMENT,str(target))
    progress.update('inventory','waiting',model_call=3,timeout=600)
    value = json.loads(target.read_text())
    assert value == dict(schema_version='java-behavior-progress-v1',phase='inventory',activity='waiting',
                         model_call=3,model_timeout_seconds=600)
    assert not list(tmp_path.glob('.comparison-progress-*'))


def test_unwritable_snapshot_is_optional(tmp_path,monkeypatch):
    target = tmp_path/'not-a-directory';target.write_text('data')
    monkeypatch.setenv(progress.ENVIRONMENT,str(target/'progress.json'))
    progress.update('analysis','indexing')
    assert target.read_text() == 'data'


@pytest.mark.parametrize('inside_folder', [False,True])
def test_progress_cannot_overwrite_or_create_files_inside_inspected_inputs(tmp_path,monkeypatch,inside_folder):
    original = tmp_path/'original';original.mkdir()
    source = original/'Original.java';source.write_text('class Original {}')
    destination = original/'progress.json' if inside_folder else source
    monkeypatch.setenv(progress.ENVIRONMENT,str(destination))
    request = dict(original=dict(sources=[str(original)] if inside_folder else [str(source)]),generated=dict(sources=[]))
    try:
        progress.protect_inputs(request)
        progress.update('analysis','indexing')
        assert source.read_text() == 'class Original {}'
        assert not (original/'progress.json').exists()
    finally:
        progress.BLOCKED_PATH.set(None)
