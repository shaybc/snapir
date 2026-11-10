"""Verify exact oversized payload capture and local, inspectable diagnostic exports."""

import json
from pathlib import Path

import pytest

from runtime.behavior_conversion.request_context import encode_request
from runtime.model_execution.diagnostics import run_model_diagnostics
from tools.run_diagnostics.request_materials import export_request_materials


def test_budget_rejection_exports_exact_materials_and_duplicate_occurrences(tmp_path):
    run = tmp_path / 'migration_runs/test-run'
    instruction = 'Exact instructions with Unicode: λ'
    payload = dict(group_id='group', sources=[
        dict(path='../../outside/Work.java', content='class Work {}'),
        dict(path='C:\\source\\Work.java', content='class Work {}')],
        schema=dict(type='object'), other_context='retained context')
    with run_model_diagnostics(run):
        with pytest.raises(ValueError, match='context budget'):
            encode_request(payload, instruction, 1)
    captures = list((run / 'reports/oversized_model_requests').iterdir())
    assert len(captures) == 2
    project = tmp_path / 'project'
    result = export_request_materials(run, project)
    assert 'exported: 2' in result[0]
    for capture in captures:
        folder = project / 'work/diagnostics/test-run' / capture.name
        for name in ('request.json', 'instructions.txt', 'metadata.json'):
            assert (folder / name).read_bytes() == (capture / name).read_bytes()
        assert (folder / 'instructions.txt').read_text(encoding='utf-8') == instruction
        request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
        assert request['schema'] == payload['schema']
        assert request['sources'] == payload['sources']
        manifest = json.loads((folder / 'materials.json').read_text())
        sources = [item for item in manifest['materials'] if item['json_pointer'].startswith('/sources/')]
        assert len(sources) == 2
        assert len({item['sha256'] for item in sources}) == 1
        assert manifest['embedded_occurrences'] > manifest['unique_content_hashes']
        for item in manifest['materials']:
            assert Path(item['file']).name == item['file']
        for item in sources:
            assert (folder / item['file']).read_text() == 'class Work {}'
        assert json.loads((folder / 'metadata.json').read_text())['delivery_status'] == 'not_sent_budget_check'
    assert not (project / 'outside').exists()
    assert export_request_materials(run, project) == result


def test_no_capture_for_fitting_request_or_outside_active_run(tmp_path):
    run = tmp_path / 'run'
    with run_model_diagnostics(run):
        encode_request(dict(message='small'), 'instruction', 1000000)
    with pytest.raises(ValueError, match='context budget'):
        encode_request(dict(message='large'), 'instruction', 1)
    assert not (run / 'reports/oversized_model_requests').exists()
    assert 'not reconstructed' in export_request_materials(run, tmp_path / 'project')[0]
    assert not (tmp_path / 'project/work/diagnostics').exists()


def test_capture_write_failure_preserves_original_budget_error(tmp_path, monkeypatch, caplog):
    original = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if path.parent.name == 'oversized_model_requests':
            raise PermissionError('capture unavailable')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    with run_model_diagnostics(tmp_path / 'run'):
        with pytest.raises(ValueError, match='exceeds its context budget'):
            encode_request(dict(group_id='example', sources=[]), 'instruction', 1)
    assert 'Unable to save oversized request materials' in caplog.text
