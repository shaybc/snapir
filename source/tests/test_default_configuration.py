"""Default profiles fix the current workflow while preserving genuine user inputs."""
import json
import pytest
import yaml
from cli import configuration_wizard as wizard
from cli.default_configuration_settings import completed_settings
from cli.default_configuration_flow import validate_settings
from models.pipeline_configuration import PipelineConfiguration
from runtime.configuration import load_configuration
from tests.test_configuration_wizard import project, collect_defaults


def test_default_wizard_saves_full_flow_without_legacy_questions(project, monkeypatch):
    collect_defaults(monkeypatch)
    monkeypatch.setenv('GEMINI_API_KEY', 'secret-test-key-never-saved')
    prompts = []
    def text(title, default='', **kwargs):
        prompts.append(title)
        if title.startswith('Config name'):
            return 'default_bank'
        return default
    monkeypatch.setattr(wizard, 'prompt_text', text)
    destination = wizard.create_default_configuration()
    assert destination.name == 'default_bank.yaml'
    saved = destination.read_text()
    data = yaml.safe_load(saved)
    profile = load_configuration(destination)
    assert profile.scoped_native_mode == 'component_first_v1'
    assert profile.conversion_strategy == 'behavior_units'
    assert profile.staged_unit_conversion and profile.cross_run_component_reuse
    assert profile.executable_verification.mode == 'test_based_v1'
    assert not profile.executable_verification.experimental_disable_facts
    assert profile.test_preparation.mode == 'ai_shared_fixtures_v1'
    assert profile.format_comparison.enabled and not profile.format_comparison.collect_facts
    assert profile.microservice.enabled and profile.microservice.require_helm_validation
    assert profile.model_provider == 'litellm'
    assert profile.model_api_key_environment == 'GEMINI_API_KEY'
    assert profile.source_workspace_id == 'default_bank'
    assert data['shared_store_root'] == '../shared'
    assert 'secret-test-key-never-saved' not in saved
    assert not any('conversion strategy' in p.lower() or 'target languages' in p.lower() for p in prompts)
    assert not list((project / 'work').glob('**/migration.db'))


def test_fixed_policy_preserves_helm_and_service_inputs():
    values = completed_settings(dict(source_workspace_id='bank', microservice={'helm_executable':'C:/tools/helm.exe'},
        deployment_environment='qa', deployment_values={'XML/Other':{'internal_base_url':'http://other:8080'}},
        scoped_native_mode='prepare', model_provider='mock'))
    profile = PipelineConfiguration.model_validate(values)
    assert profile.microservice.helm_executable == 'C:/tools/helm.exe'
    assert profile.microservice.enabled and profile.microservice.require_helm_validation
    assert profile.deployment_environment == 'qa'
    assert profile.deployment_values['XML/Other']['internal_base_url'] == 'http://other:8080'
    assert profile.scoped_native_mode == 'component_first_v1' and profile.model_provider == 'litellm'


def test_review_cannot_save_a_different_map_identity(tmp_path, monkeypatch):
    monkeypatch.setattr('tools.composer_mapper_tools.indexed_analysis.is_indexed_map', lambda _: True)
    root = tmp_path / 'map'; root.mkdir()
    (root / 'vault-manifest.json').write_text(json.dumps({'workspace_id':'original'}))
    with pytest.raises(ValueError, match='workspace ID'):
        validate_settings(dict(existing_composer_map='map', source_workspace_id='changed'), tmp_path)
    validate_settings(dict(existing_composer_map='map', source_workspace_id='original'), tmp_path)


def test_default_menu_returns_without_starting_conversion(monkeypatch):
    from cli import interactive
    from cli.main import main
    monkeypatch.setattr(interactive, 'is_interactive', lambda: True)
    choices = iter(['create_default_config', 'exit'])
    monkeypatch.setattr(interactive, 'select_option', lambda *a, **k: next(choices))
    calls = []
    monkeypatch.setattr('cli.main.create_default_configuration', lambda: calls.append('created'))
    monkeypatch.setattr('cli.main.run_pipeline', lambda *a: pytest.fail('Unexpected migration'))
    assert main([]) == 0 and calls == ['created']


def test_default_wizard_cancellation_does_not_write(project, monkeypatch):
    from cli.interactive import SelectionCancelled
    collect_defaults(monkeypatch)
    def cancel(*args, **kwargs):
        raise SelectionCancelled(input_closed=True)
    monkeypatch.setattr(wizard, 'prompt_text', cancel)
    assert wizard.create_default_configuration() is None
    assert not list(project.glob('configs/*.yaml'))


def test_default_environment_seeds_matching_microservice_values_once(tmp_path):
    from runtime.service_generation.deployment_configuration import load_deployment, write_deployment
    profile = PipelineConfiguration.model_validate(completed_settings(dict(source_workspace_id='bank',
        deployment_environment='qa',service_environments={'qa':dict(namespace='bank-qa',service_port=9090)})))
    item = dict(project=str(tmp_path),channel='XML',operation_id='Flow',payload={})
    deployment = load_deployment(item,profile=profile)
    assert deployment.deployment.namespace == 'bank-qa' and deployment.http.port == 9090
    assert deployment.http.serviceName == 'xml-flow'
    deployment.http.port = 9191
    deployment.deployment.namespace = 'edited'
    write_deployment(tmp_path / 'values.yaml',deployment)
    assert load_deployment(item,profile=profile) == deployment
