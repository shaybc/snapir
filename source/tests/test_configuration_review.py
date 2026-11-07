"""Exercise draft editing, bounded review, real keyboard navigation and start side effects."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from cli import configuration_wizard as wizard
from cli import interactive
from cli.configuration_inputs import WizardBack
from cli.configuration_review import summary_lines, wrapped_summary, safe_value
from cli.main import main
from tests.test_configuration_wizard import project, collect_defaults


def test_back_discards_unfinished_section_and_preserves_committed_answers(project, monkeypatch):
    collect_defaults(monkeypatch)
    text = wizard.prompt_text
    attempts, restored = 0, []
    def answer(title, default='', **kwargs):
        nonlocal attempts
        if title == 'mapper_jar':
            attempts += 1
            if attempts == 1:
                raise WizardBack
        if title.startswith('Config name'):
            restored.append(default)
        return text(title, default, **kwargs)
    monkeypatch.setattr(wizard, 'prompt_text', answer)
    destination = wizard.create_configuration()
    assert destination.name == 'new_config.yaml'
    assert restored == ['', 'new_config']
    assert attempts == 2


def test_review_edit_preserves_fields_and_does_not_repeat_discovery(project, monkeypatch):
    collect_defaults(monkeypatch)
    discover, calls = wizard.discover_operations, []
    def discovery(*args):
        calls.append(args)
        return discover(*args)
    monkeypatch.setattr(wizard, 'discover_operations', discovery)
    reviews, edits, saved = 0, [], []
    original_save = wizard.save_configuration
    monkeypatch.setattr(wizard, 'save_configuration', lambda *args, **kwargs:
                        saved.append(args) or original_save(*args, **kwargs))
    def menu(title, options, **kwargs):
        nonlocal reviews
        if title == 'Review configuration':
            assert options[0][0] == 'edit'
            assert not saved
            reviews += 1
            return 'edit' if reviews <= 2 else 'save'
        if title == 'Edit a section':
            choice = '3' if not edits else '7'
            edits.append(choice)
            return choice
        return options[0][0]
    monkeypatch.setattr(wizard, 'select_option', menu)
    text = wizard.prompt_text
    model_defaults = []
    def answer(title, default='', **kwargs):
        if title == 'model_name':
            model_defaults.append(default)
            return 'openai/edited-model' if len(model_defaults) == 2 else default
        return text(title, default, **kwargs)
    monkeypatch.setattr(wizard, 'prompt_text', answer)
    destination = wizard.create_configuration()
    data = yaml.safe_load(destination.read_text())
    assert data['model_name'] == 'openai/edited-model'
    assert data['channels'] == ['WEB'] and data['include_operations'] == ['WebOperation']
    assert len(calls) == 1 and len(saved) == 1
    assert model_defaults == ['openai/your-model-name', 'openai/your-model-name']


def test_edit_source_requires_scope_review_and_removes_stale_checks(project, monkeypatch):
    collect_defaults(monkeypatch)
    alternate = project / 'alternate'
    from tests.test_configuration_wizard import operation_file
    operation_file(alternate, 'new', 'NEW', 'NewOperation')
    text, visits, reviews = wizard.prompt_text, [], 0
    def answer(title, default='', **kwargs):
        if title == 'source_root' and reviews:
            return '../alternate'
        return text(title, default, **kwargs)
    def multiple(title, options, **kwargs):
        visits.append((title, kwargs['initial']))
        if reviews and title in {'Select channels', 'Select operations'}:
            assert kwargs['initial'] == []
        return [options[0][0]]
    def menu(title, options, **kwargs):
        nonlocal reviews
        if title == 'Review configuration':
            reviews += 1
            return 'edit' if reviews == 1 else 'save'
        if title == 'Edit a section':
            return '0'
        return options[0][0]
    monkeypatch.setattr(wizard, 'prompt_text', answer)
    monkeypatch.setattr(wizard, 'select_multiple', multiple)
    monkeypatch.setattr(wizard, 'select_option', menu)
    data = yaml.safe_load(wizard.create_configuration().read_text())
    assert data['channels'] == ['NEW'] and data['include_operations'] == ['NewOperation']
    assert len(visits) == 6


def test_map_mode_toggle_restores_answers_but_saves_only_active_mode(project, monkeypatch):
    collect_defaults(monkeypatch)
    vault = project / 'mapped'
    (vault / 'analysis').mkdir(parents=True)
    (vault / 'analysis/channel-operation-registry.md').write_text('WEB')
    text, reviews, modes = wizard.prompt_text, 0, []
    def answer(title, default='', **kwargs):
        if title == 'Existing Composer map folder':
            return '../mapped'
        return text(title, default, **kwargs)
    def menu(title, options, **kwargs):
        nonlocal reviews
        if title == 'Review configuration':
            reviews += 1
            return 'edit' if reviews < 3 else 'save'
        if title == 'Edit a section':
            return '1'
        if title == 'Composer map':
            modes.append(kwargs.get('initial'))
            return 'existing' if reviews == 1 else 'create'
        return options[0][0]
    monkeypatch.setattr(wizard, 'prompt_text', answer)
    monkeypatch.setattr(wizard, 'select_option', menu)
    data = yaml.safe_load(wizard.create_configuration().read_text())
    assert 'mapper_jar' in data and 'existing_composer_map' not in data
    assert modes == [None, 'create', 'existing']


def test_cancel_returns_without_writing_and_continue_retains_answers(project, monkeypatch):
    collect_defaults(monkeypatch)
    reviews, discards = 0, 0
    def menu(title, options, **kwargs):
        nonlocal reviews, discards
        if title == 'Review configuration':
            reviews += 1
            return 'cancel'
        if title == 'Discard unsaved configuration?':
            discards += 1
            return 'continue' if discards == 1 else 'discard'
        return options[0][0]
    monkeypatch.setattr(wizard, 'select_option', menu)
    assert wizard.create_configuration() is None
    assert reviews == 2 and discards == 2
    assert not (project / 'configs').exists()


def test_empty_selection_retries_without_losing_other_sections(project, monkeypatch):
    collect_defaults(monkeypatch)
    multiple, empty = wizard.select_multiple, True
    def choose(title, options, **kwargs):
        nonlocal empty
        if title == 'Select channels' and empty:
            return []
        if title == 'Select target languages' and empty:
            empty = False
            return []
        if empty:
            return []
        return multiple(title, options, **kwargs)
    monkeypatch.setattr(wizard, 'select_multiple', choose)
    assert yaml.safe_load(wizard.create_configuration().read_text())['channels'] == ['WEB']


def test_save_validation_failure_routes_back_to_relevant_section(project, monkeypatch):
    collect_defaults(monkeypatch)
    save, attempts = wizard.save_configuration, 0
    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError('model_name must be corrected')
        return save(*args, **kwargs)
    monkeypatch.setattr(wizard, 'save_configuration', fail_once)
    seen, prompt = [], wizard.prompt_text
    def text(title, default='', **kwargs):
        if attempts and title == 'model_name':
            seen.append(default)
            return 'openai/corrected'
        return prompt(title, default, **kwargs)
    monkeypatch.setattr(wizard, 'prompt_text', text)
    assert yaml.safe_load(wizard.create_configuration().read_text())['model_name'] == 'openai/corrected'
    assert attempts == 2 and seen == ['openai/your-model-name']


def test_summary_is_bounded_and_redacts_credentials(monkeypatch):
    monkeypatch.setenv('SNAPIR_LLM_API_KEY', 'super-secret-value')
    lines = summary_lines(dict(include_operations=[f'Operation{i}' for i in range(10000)],
        model_base_url='https://user:password@example.test/v1?api_key=abc#token',
        model_api_key_environment='SNAPIR_LLM_API_KEY', external_dependencies=[{'password': 'embedded-secret'}]))
    text = '\n'.join(lines)
    assert len(text) < 1000 and '10000 selected' in text
    assert all(secret not in text for secret in ('password@', 'api_key=abc', 'embedded-secret', 'super-secret-value'))
    assert 'SNAPIR_LLM_API_KEY' in text and 'example.test/v1' in text
    path = 'C:/' + 'very-long-folder/' * 20
    wrapped = wrapped_summary([path], 40)
    assert all(len(line) <= 40 for line in wrapped.splitlines())
    assert ''.join(line.strip() for line in wrapped.splitlines()) == path


def test_text_keyboard_clear_back_and_eof(monkeypatch):
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    with create_pipe_input() as pipe:
        session = PromptSession(input=pipe, output=DummyOutput())
        monkeypatch.setattr('prompt_toolkit.prompt', session.prompt)
        pipe.send_text('\r')
        assert wizard.prompt_text('Path', 'long/default', heading='Create configuration') == 'long/default'
        pipe.send_text('\x15\r')
        assert wizard.prompt_text('Optional path', 'long/default', heading='Create configuration') == ''
        pipe.send_text('\x02')
        with pytest.raises(WizardBack):
            wizard.prompt_text('Path', 'long/default', heading='Create configuration', allow_back=True)
        pipe.send_text('\x04')
        with pytest.raises(interactive.SelectionCancelled) as error:
            wizard.prompt_text('Path', '', heading='Create configuration')
        assert error.value.input_closed


@pytest.mark.parametrize('action', ['start', 'cancel', 'back'])
def test_interactive_start_review_precedes_run_creation(tmp_path, monkeypatch, action):
    monkeypatch.setattr(interactive, 'is_interactive', lambda: True)
    selections = iter(['start', 'exit'])
    monkeypatch.setattr(interactive, 'select_option', lambda *_: next(selections))
    monkeypatch.setattr('cli.main.load_configuration', lambda _: SimpleNamespace(output_root=str(tmp_path)))
    monkeypatch.setattr('cli.main.choose_run_name', lambda *_: 'named-run')
    confirmations, calls = [], []
    def confirm(path, profile, run_id):
        assert not calls
        confirmations.append(path)
        return 'start' if len(confirmations) > 1 else action
    monkeypatch.setattr('cli.main.confirm_migration_start', confirm)
    monkeypatch.setattr('cli.main.select_configuration', lambda **kwargs: 'second.yaml')
    monkeypatch.setattr('cli.main.run_pipeline', lambda profile, run_id, configuration_path: calls.append(run_id) or tmp_path)
    assert main(['--config', 'first.yaml']) == 0
    assert len(calls) == (0 if action == 'cancel' else 1)
    assert confirmations == (['first.yaml', 'second.yaml'] if action == 'back' else ['first.yaml'])


def test_start_review_defaults_back_and_escape_cancels(monkeypatch):
    from cli.migration_start_review import confirm_migration_start
    def menu(title, options, **kwargs):
        assert options[0][0] == 'back'
        assert 'Run name: named-run' in '\n'.join(kwargs['details'])
        assert 'Configuration: test.yaml' in kwargs['details']
        assert f'Run folder: {Path("runs").resolve() / "named-run"}' in kwargs['details']
        raise interactive.SelectionCancelled
    monkeypatch.setattr('cli.migration_start_review.select_option', menu)
    assert confirm_migration_start('test.yaml', SimpleNamespace(source_root='demo', output_root='runs'), 'named-run') == 'cancel'


def test_wizard_checkbox_defaults_and_back_key(monkeypatch):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from cli.multiselect import select_multiple
    with create_pipe_input() as pipe:
        monkeypatch.setattr('prompt_toolkit.application.Application', lambda **kwargs:
                            Application(**kwargs, input=pipe, output=DummyOutput()))
        options = [('one', 'One'), ('two', 'Two')]
        pipe.send_text('\r')
        assert select_multiple('Channels', options, initial=['one'], heading='Create configuration',
                               allow_back=True) == ['one']
        pipe.send_text('\x02')
        with pytest.raises(WizardBack):
            select_multiple('Channels', options, initial=['one'], heading='Create configuration', allow_back=True)


@pytest.mark.parametrize('rows', [12, 16])
def test_review_scrolls_settings_and_keeps_actions_visible_in_small_terminal(monkeypatch, rows):
    import asyncio
    from prompt_toolkit.application import Application
    from prompt_toolkit.data_structures import Size
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    class SmallTerminal(DummyOutput):
        def get_size(self):
            return Size(rows=rows, columns=55)
    snapshots, failures = [], []
    with create_pipe_input() as pipe:
        def rendered(app):
            if app.is_done:
                return
            try:
                header, summary, actions, footer = app.layout.container.children
                assert header in app.layout.visible_windows and footer in app.layout.visible_windows
                assert actions.render_info.displayed_lines[:5] == [0, 1, 2, 3, 4]
                snapshots.append(summary.vertical_scroll)
                if len(snapshots) == 1:
                    pipe.send_text('\x1b[6~')
                else:
                    assert snapshots[-1] > snapshots[0]
                    pipe.send_text('\r')
            except BaseException as exc:
                failures.append(exc)
                app.exit(result='cancel')
        def application(**kwargs):
            app = Application(**kwargs, input=pipe, output=SmallTerminal(), after_render=rendered)
            app.pre_run_callables.append(lambda: asyncio.get_running_loop().call_later(3,
                lambda: app.exit(exception=AssertionError('Review did not finish')) if not app.is_done else None))
            return app
        monkeypatch.setattr('prompt_toolkit.application.Application', application)
        result = interactive.select_option('Review configuration', [('edit', 'Edit a section'),
            ('save', 'Save configuration'), ('operations', 'View all selected operations'), ('back', 'Back'), ('cancel', 'Cancel')],
            heading='Review configuration: test', details=[f'Setting {i}: value' for i in range(100)])
    if failures:
        raise failures[0]
    assert result == 'edit'


def test_large_operation_review_can_filter_without_changing_choices(monkeypatch):
    from prompt_toolkit.application import Application
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    options = [(str(i), f'Operation{i}') for i in range(10000)]
    with create_pipe_input() as pipe:
        monkeypatch.setattr('prompt_toolkit.application.Application', lambda **kwargs:
                            Application(**kwargs, input=pipe, output=DummyOutput()))
        pipe.send_text('Operation9999\r')
        assert interactive.select_option('Selected operations', options, heading='Review configuration', filterable=True) == '9999'
    assert len(options) == 10000
