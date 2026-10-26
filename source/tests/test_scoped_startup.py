"""Exercise normal scoped startup without falling through legacy planning readers."""

import json
import subprocess
from pathlib import Path

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import resolve_java_home
from runtime.workspace_paths import run_database_path, run_profile_path, run_report_path
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.runs import get_run
from tools.workspace_intake_tools.mapper_generation import mapper_command
from test_scoped_vault_identity import scoped_mapper


def settings(tmp_path, layout='legacy'):
    jar = tmp_path / 'mapper.jar'
    jar.touch()
    root = tmp_path / 'source'
    root.mkdir(exist_ok=True)
    return dict(COMPOSER_MAPPER_JAR=str(jar), COMPOSER_ROOT=str(root), VAULT_ROOT=str(tmp_path / 'vault'),
        COMPOSER_MAPPER_VAULT_LAYOUT=layout, SOURCE_WORKSPACE_ID='bank', RUN_MODE='single_channel', TARGET_CHANNELS=['SME'])


def test_profile_preserves_legacy_default_and_scoped_setting_roundtrip():
    assert PipelineConfiguration().mapper_vault_layout == 'legacy'
    profile = PipelineConfiguration(mapper_vault_layout='scoped', source_workspace_id='bank')
    restored = PipelineConfiguration.model_validate_json(profile.model_dump_json())
    assert restored.mapper_vault_layout == 'scoped' and restored.source_workspace_id == 'bank'


@pytest.mark.parametrize('identity', [None, '', '   '])
def test_scoped_profile_requires_nonblank_workspace_identity(identity):
    with pytest.raises(ValueError):
        PipelineConfiguration(mapper_vault_layout='scoped', source_workspace_id=identity)


@pytest.mark.parametrize('layout', ['legacy', 'scoped'])
@pytest.mark.parametrize('filter_channel', [True, False])
def test_commands_preserve_legacy_flags_and_scoped_identity(tmp_path, layout, filter_channel):
    values = settings(tmp_path, layout)
    expected = ['java', '-jar', values['COMPOSER_MAPPER_JAR'], '--root', values['COMPOSER_ROOT'], '--vault', values['VAULT_ROOT']]
    if layout == 'scoped':
        expected += ['--vault-layout', 'scoped', '--workspace-id', 'bank', '--md', 'true']
    else:
        expected += ['--md']
    if filter_channel:
        expected += ['--channel', 'SME']
    assert mapper_command(values, markdown=True, filter_channel=filter_channel) == expected
    if layout == 'legacy':
        standalone = mapper_command(values)
        assert '--md' not in standalone and standalone[-2:] == ['--channel', 'SME']


def test_command_retains_output_and_missing_jar_validation(tmp_path):
    values = settings(tmp_path, 'scoped')
    vault = Path(values['VAULT_ROOT'])
    vault.mkdir()
    (vault / 'existing.md').write_text('preserve evidence')
    with pytest.raises(ValueError, match='empty'):
        mapper_command(values)
    assert (vault / 'existing.md').read_text() == 'preserve evidence'
    values['COMPOSER_MAPPER_JAR'] = str(tmp_path / 'missing.jar')
    with pytest.raises(ValueError, match='existing COMPOSER_MAPPER_JAR'):
        mapper_command(values)


def test_real_pipeline_start_and_resume_use_scoped_intake(tmp_path, scoped_mapper, monkeypatch):
    from runtime import pipeline_runner
    from runtime.checkpoints import resume_pipeline
    from test_scoped_closure import workspace
    try:
        java_home = resolve_java_home(25)
    except ValueError as exc:
        pytest.skip(str(exc))
    jar = tmp_path / 'mapper.jar'
    subprocess.run([str(Path(java_home) / 'bin/jar'), '--create', '--file', str(jar),
        '--main-class', 'il.co.dcd.composermapper.Main', '-C', str(scoped_mapper), '.'], check=True, capture_output=True)
    source = tmp_path / 'source'
    workspace(source)
    before = {path: path.read_bytes() for path in source.rglob('*') if path.is_file()}
    profile = PipelineConfiguration(source_root=str(source), mapper_jar=str(jar), mapper_vault_layout='scoped',
        source_workspace_id='test-startup', scoped_java_project='.', output_root=str(tmp_path / 'runs'),
        channels=['SME'], include_operations=None, exclude_operations=None, conversion_strategy='behavior_units',
        java_version=25, java_home=java_home, model_provider='mock', classpath_jars=[], eclipse_classpath_variables={})
    def forbidden(*args, **kwargs):
        pytest.fail('Scoped intake entered legacy context/planning analysis')
    monkeypatch.setattr(pipeline_runner, 'build_all_context_hierarchies', forbidden)
    monkeypatch.setattr(pipeline_runner, 'get_operations_for_planning', forbidden)
    directory = pipeline_runner.run_pipeline(profile, 'scoped-start')
    manifest = json.loads((directory / 'vault/vault-manifest.json').read_text())
    assert manifest['vault_schema_version'] == 3 and manifest['workspace_id'] == 'test-startup'
    # Behavior-unit mapping keeps the XML channel available while selection stays SME.
    assert 'XML' in manifest['channels']
    with get_connection(str(run_database_path(directory))) as conn:
        run = get_run(conn, 'scoped-start')
        assert run['current_phase'] == 'scoped_inventory_ready'
        selected = conn.execute('SELECT DISTINCT channel FROM scoped_operation_contexts WHERE selected=1').fetchall()
        assert [row[0] for row in selected] == ['SME']
    saved = PipelineConfiguration.model_validate_json(run_profile_path(directory).read_text())
    assert saved.mapper_vault_layout == 'scoped'
    from cli.discovery import discover_runs
    assert any('scoped-start' == value for value, label in discover_runs(profile.output_root, resumable_only=True))
    assert resume_pipeline(profile.output_root, 'scoped-start') == directory
    acceptance = json.loads(run_report_path(directory, 'scoped_acceptance.json').read_text())
    assert not acceptance['conversion_enabled']
    with get_connection(str(run_database_path(directory))) as conn:
        assert get_run(conn, 'scoped-start')['current_phase'] == 'conversion_scoped_gated'
    assert {path: path.read_bytes() for path in source.rglob('*') if path.is_file()} == before
    with pytest.raises(FileExistsError):
        pipeline_runner.run_pipeline(profile, 'scoped-start')
