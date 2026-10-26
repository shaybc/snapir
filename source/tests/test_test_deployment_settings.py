"""Verify saved deployment targets and CLI defaults without remote side effects."""

from copy import deepcopy

import pytest
import yaml
from pydantic import ValidationError

import constants
from cli.test_deployment_settings import collect_test_deployment_settings
from models.pipeline_configuration import PipelineConfiguration
from models.test_deployment_settings import TestDeploymentSettings as DeploymentSettings
from runtime.configuration import load_configuration


def test_defaults_come_from_constants_and_instances_are_independent(monkeypatch):
    defaults = deepcopy(constants.TEST_DEPLOYMENT_DEFAULTS)
    defaults.update(service_base_url="https://apps.example.test")
    monkeypatch.setattr(constants, "TEST_DEPLOYMENT_DEFAULTS", defaults)
    first, second = PipelineConfiguration(), PipelineConfiguration()
    assert first.test_deployment.model_dump(mode="json") == defaults
    first.test_deployment.service_base_url = "https://changed.example.test"
    assert second.test_deployment.service_base_url == "https://apps.example.test"
    assert defaults["service_base_url"] == "https://apps.example.test"


def test_collector_prompts_for_all_settings_with_constants_defaults():
    prompts = []
    def prompt(title, default):
        prompts.append((title, default))
        return default
    result = collect_test_deployment_settings(prompt)
    assert result == {"test_deployment": deepcopy(constants.TEST_DEPLOYMENT_DEFAULTS)}
    assert len(prompts) == len(DeploymentSettings.model_fields) == 3
    assert ("Test service base URL", constants.TEST_DEPLOYMENT_DEFAULTS["service_base_url"]) in prompts
    assert ("External service port (auto or number)", "auto") in prompts


def test_collector_retries_invalid_urls_and_ports(capsys):
    values = {
        "External service port (auto or number)": iter(["wrong", "70000", "8443"]),
        "Test service base URL": iter(["not-a-url", "https://apps.example.test"]),
    }
    def prompt(title, default):
        return next(values[title]) if title in values else default
    result = collect_test_deployment_settings(prompt)["test_deployment"]
    assert result["service_external_port"] == 8443
    assert result["service_base_url"] == "https://apps.example.test"
    assert "validation error" in capsys.readouterr().out


def test_settings_round_trip_preserves_test_address(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "mapper.jar").touch()
    filename = tmp_path / "profile.yaml"
    filename.write_text(yaml.safe_dump(dict(source_root="source", mapper_jar="mapper.jar", test_deployment=dict(
        service_base_url="https://apps.example.test", service_external_port=8443,
        service_route_pattern="{service_name}"))))
    profile = load_configuration(filename)
    assert profile.test_deployment.model_dump() == dict(
        service_base_url="https://apps.example.test", service_external_port=8443,
        service_route_pattern="{service_name}")
    assert PipelineConfiguration.model_validate_json(profile.model_dump_json()) == profile


@pytest.mark.parametrize("values", [{"service_external_port": 0}, {"service_external_port": 65536},
                                    {"service_base_url": "ftp://apps.test"}, {"unknown": True}])
def test_invalid_values_rejected(values):
    with pytest.raises(ValidationError):
        DeploymentSettings(**values)


def test_cancellation_does_not_return_partial_settings():
    from cli.interactive import SelectionCancelled
    count = 0
    def prompt(title, default):
        nonlocal count
        count += 1
        if count == 3:
            raise SelectionCancelled
        return default
    with pytest.raises(SelectionCancelled):
        collect_test_deployment_settings(prompt)
