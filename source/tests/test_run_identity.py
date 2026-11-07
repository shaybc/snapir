"""Verify named runs and their read-only, timestamped CLI presentation."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from cli import interactive, run_naming
from cli.discovery import discover_runs
from cli.main import main
from cli.run_presentation import read_run_summary, select_run
from runtime.run_identity import record_resume_started
from tests.test_cli_interactive import make_run


@pytest.mark.parametrize('name', ['', '../outside', 'has spaces', 'CON', 'com1', 'a' * 101])
def test_invalid_run_names_create_nothing(tmp_path, name):
    with pytest.raises(ValueError):
        run_naming.validate_run_name(str(tmp_path), name)
    assert list(tmp_path.iterdir()) == []


def test_run_prompt_retries_duplicate_and_invalid_names(tmp_path, monkeypatch):
    (tmp_path / 'existing').mkdir()
    answers = iter(['existing', 'invalid name', 'my-bank-test'])
    monkeypatch.setattr(run_naming, 'prompt_text', lambda *args, **kwargs: next(answers))
    assert run_naming.choose_run_name('huge_test.yaml', str(tmp_path)) == 'my-bank-test'
    assert [path.name for path in tmp_path.iterdir()] == ['existing']


def test_suggested_name_is_safe_bounded_and_unique(tmp_path):
    configuration = tmp_path / ('Long name ' * 20 + '.yaml')
    first, second = (run_naming.suggested_run_name(configuration) for _ in range(2))
    assert len(first) <= 100 and first != second
    assert ' ' not in first
    assert run_naming.validate_run_name(str(tmp_path), first).name == first


def test_named_start_reviews_destination_and_saves_origin_before_intake(tmp_path, monkeypatch):
    from models.pipeline_configuration import PipelineConfiguration
    profile = PipelineConfiguration(output_root=str(tmp_path), model_provider='mock')
    monkeypatch.setattr(interactive, 'is_interactive', lambda: True)
    monkeypatch.setattr('cli.main.is_interactive', lambda: True)
    monkeypatch.setattr('cli.main.load_configuration', lambda _: profile)
    monkeypatch.setattr(run_naming, 'prompt_text', lambda *args, **kwargs: 'bank-pilot')
    configuration = str(tmp_path / 'configs/huge_test.yaml')

    def confirm(path, saved_profile, name):
        assert (path, saved_profile, name) == (configuration, profile, 'bank-pilot')
        assert not (tmp_path / name).exists()
        return 'start'

    def unavailable(*args):
        raise RuntimeError('Database unavailable')

    monkeypatch.setattr('cli.main.confirm_migration_start', confirm)
    monkeypatch.setattr('runtime.pipeline_runner.get_connection', unavailable)
    assert main(['start', '--config', configuration]) == 1
    identity = json.loads((tmp_path / 'bank-pilot/state/run_identity.json').read_text())
    assert identity['run_id'] == 'bank-pilot'
    assert identity['configuration_name'] == 'huge_test'
    assert identity['configuration_path'] == configuration
    assert datetime.fromisoformat(identity['created_at']).tzinfo is not None
    assert list(tmp_path.iterdir()) == [tmp_path / 'bank-pilot']


def test_cancel_run_name_creates_no_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(interactive, 'is_interactive', lambda: True)
    monkeypatch.setattr('cli.main.is_interactive', lambda: True)
    monkeypatch.setattr('cli.main.load_configuration', lambda _: SimpleNamespace(output_root=str(tmp_path)))

    def cancel(*args, **kwargs):
        raise interactive.SelectionCancelled

    monkeypatch.setattr(run_naming, 'prompt_text', cancel)
    monkeypatch.setattr('cli.main.run_pipeline', lambda *_: pytest.fail('Created cancelled run'))
    assert main(['start', '--config', 'huge_test.yaml']) == 130
    assert list(tmp_path.iterdir()) == []


def test_summaries_sort_by_gate_and_resume_activity_without_mutation(tmp_path, monkeypatch):
    from runtime.human_gates import record_decision
    first, second = make_run(tmp_path, 'first'), make_run(tmp_path, 'second')
    for directory in (first, second):
        path = directory / 'state/run_identity.json'
        identity = json.loads(path.read_text())
        identity['created_at'] = '2026-11-07T10:00:00+00:00'
        path.write_text(json.dumps(identity))
    monkeypatch.setattr('runtime.human_gates.utc_now', lambda: '2026-11-07T11:00:00+00:00')
    with sqlite3.connect(first / 'state/migration.db') as conn:
        record_decision(conn, 'first', 0, 'plan evidence', 'approved')
    before = {p: p.read_bytes() for p in first.rglob('*') if p.is_file()}
    summary = read_run_summary(first)
    assert summary['latest'] == datetime.fromisoformat('2026-11-07T11:00:00+00:00')
    assert 'Conversion plan approved' in '\n'.join(summary['details'])
    assert 'Not yet' in '\n'.join(summary['details'])
    assert [name for name, _ in discover_runs(str(tmp_path))] == ['first', 'second']
    assert {p: p.read_bytes() for p in first.rglob('*') if p.is_file()} == before
    monkeypatch.setattr('runtime.run_identity.utc_now', lambda: '2026-11-07T12:00:00+00:00')
    record_resume_started(second)
    assert [name for name, _ in discover_runs(str(tmp_path))] == ['second', 'first']
    assert 'Last resumed: Not yet' not in '\n'.join(read_run_summary(second)['details'])


@pytest.mark.parametrize('columns', [55, 120])
def test_run_picker_details_follow_highlight_and_filter(tmp_path, monkeypatch, columns):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from prompt_toolkit.data_structures import Size
    make_run(tmp_path, 'first')
    make_run(tmp_path, 'second')
    options = discover_runs(str(tmp_path))
    details_seen = []

    class TerminalOutput(DummyOutput):
        def get_size(self):
            return Size(rows=24, columns=columns)

    def application(**kwargs):
        layout = kwargs['layout']
        # Evaluate rendered controls at the chosen entry, exercising wrapped details.
        from prompt_toolkit.layout import Window
        for container in layout.walk():
            if isinstance(container, Window) and hasattr(container.content, 'text') and callable(container.content.text):
                original = container.content.text

                def capture(original=original):
                    value = original()
                    if isinstance(value, str) and 'Configuration file:' in value:
                        details_seen.append(value)
                    return value

                container.content.text = capture
        return Application(**kwargs, input=pipe, output=TerminalOutput())

    with create_pipe_input() as pipe:
        monkeypatch.setattr('prompt_toolkit.application.Application', application)
        pipe.send_text('first\r')
        assert select_run('Select a run', options, output_root=str(tmp_path)) == 'first'
    assert any('Run: first' in value and 'bank_demo' in value for value in details_seen)


def test_approval_preselects_same_run_for_resume(tmp_path, monkeypatch):
    from tests.test_gate_menu import saved_run
    directory = saved_run(tmp_path / 'work/migration_runs', 'my-bank', 'gate_2_pending')
    (directory / 'state/profile.json').write_text('{}')
    monkeypatch.setattr(interactive, 'project_root', lambda: tmp_path)
    monkeypatch.setattr(interactive, 'is_interactive', lambda: True)
    monkeypatch.setattr('cli.status_discovery.constants.OUTPUT_ROOT', 'work/migration_runs')
    choices = iter(['approve', str(directory), 'resume', str(directory), 'exit'])
    resumed = []

    def select(title, options, **kwargs):
        if title == 'Select a run':
            assert kwargs['initial'] == str(directory)
            assert any('Gate 2 approved' in line for line in kwargs['details'](str(directory)))
        return next(choices)

    monkeypatch.setattr(interactive, 'select_option', select)
    monkeypatch.setattr('cli.main.resume_pipeline', lambda root, name: resumed.append(name) or directory)
    assert main([]) == 0
    assert resumed == ['my-bank']
