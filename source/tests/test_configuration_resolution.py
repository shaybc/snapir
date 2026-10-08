"""Verify central defaults, explicit overrides and persisted effective settings."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import constants
from models.pipeline_configuration import PipelineConfiguration
from runtime.configuration import load_configuration
from runtime.shared_libraries.registry import conversion_hash
from runtime.service_generation.runner import generation_settings_identity
from tools.workspace_intake_tools.env_loader import load_env_with_fallbacks
from tools.workspace_intake_tools.run_factory import create_run_config


def test_model_defaults_reference_central_values():
    profile = PipelineConfiguration()
    for field, key in (("source_root", "COMPOSER_ROOT"), ("mapper_jar", "COMPOSER_MAPPER_JAR"),
                       ("output_root", "OUTPUT_ROOT"), ("model_name", "AGENT_MODEL"),
                       ("max_agent_task_retries", "MAX_AGENT_TASK_RETRIES"),
                       ("shared_library_min_usage", "SHARED_LIBRARY_MIN_USAGE"),
                       ("max_operations_per_batch", "MAX_OPERATIONS_PER_BATCH")):
        assert getattr(profile, field) == getattr(constants, key)


def test_false_empty_zero_null_and_partial_gate_overrides():
    profile = PipelineConfiguration(auto_rerun_impacted_operations=False, enable_git=False,
        model_base_url="", inter_batch_delay_secs=0, include_operations=[],
        exclude_operations=None, approved_maven_repository_urls=[], gate_policies={"2": "skip"})
    assert profile.auto_rerun_impacted_operations is False
    assert profile.inter_batch_delay_secs == 0
    assert profile.include_operations == []
    assert profile.exclude_operations is None
    assert profile.model_base_url == ""
    assert profile.gate_policies == {"1": "human", "2": "skip", "3": "human", "4": "human"}


def test_nested_defaults_are_independent(monkeypatch):
    baseline = {"WEB/Op": {"health_paths": {"liveness": "/health"}}}
    monkeypatch.setattr(constants, "DEPLOYMENT_VALUES", deepcopy(baseline))
    first, second = PipelineConfiguration(), PipelineConfiguration()
    first.deployment_values["WEB/Op"]["health_paths"]["liveness"] = "/changed"
    first.channels.append("OTHER")
    first.gate_policies["1"] = "skip"
    assert second.deployment_values == baseline
    assert constants.DEPLOYMENT_VALUES == baseline
    assert second.channels == constants.TARGET_CHANNELS
    assert second.gate_policies == constants.GATE_POLICIES


@pytest.mark.parametrize("values", [{"target_languages": ["nodejs"]}, {"unknown": True},
                                    {"model_api_key": "forbidden"}, {"gate_policies": {"5": "skip"}}])
def test_unsupported_fields_and_capabilities(values):
    with pytest.raises(ValidationError):
        PipelineConfiguration(**values)


def test_default_and_yaml_path_bases_ignore_current_directory(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "mapper.jar").touch()
    filename = tmp_path / "profile.yaml"
    filename.write_text(yaml.safe_dump(dict(source_root="source", mapper_jar="mapper.jar")))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    profile = load_configuration(filename)
    assert profile.source_root == str(source.resolve())
    assert profile.mapper_jar == str((tmp_path / "mapper.jar").resolve())
    assert profile.output_root == str((Path(constants.__file__).parent.parent / constants.OUTPUT_ROOT).resolve())
    filename.write_text(yaml.safe_dump(dict(source_root="source", mapper_jar="mapper.jar", output_root="out")))
    assert load_configuration(filename).output_root == str((tmp_path / "out").resolve())


def test_snapshot_retains_effective_defaults_after_globals_change(monkeypatch):
    profile = PipelineConfiguration(gate_policies={"2": "automatic"}, model_name="saved-model")
    snapshot = profile.model_dump_json()
    monkeypatch.setattr(constants, "GATE_POLICIES", {str(n): "skip" for n in range(1, 5)})
    monkeypatch.setattr(constants, "AGENT_MODEL", "changed-model")
    assert PipelineConfiguration.model_validate_json(snapshot) == profile


def test_intake_settings_preserve_overrides_and_exclude_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-secret")
    filename = tmp_path / ".env"
    filename.write_text("AUTO_RERUN_IMPACTED_OPERATIONS=false\nINTER_BATCH_DELAY_SECS=0\nMAX_AGENT_TASK_RETRIES=7\nCOMPOSER_ROOT=source\n")
    settings = load_env_with_fallbacks(str(filename))
    config = create_run_config(settings, "test-run")
    assert config.auto_rerun_impacted_operations is False
    assert config.inter_batch_delay_secs == 0
    assert config.max_agent_task_retries == 7
    assert config.source_root == str((tmp_path / "source").resolve())
    assert "LITELLM_API_KEY" not in settings
    assert "test-secret" not in config.model_dump_json()
    assert "test-secret" not in PipelineConfiguration().model_dump_json()


def test_cache_identity_changes_with_resolved_endpoint_and_build_policy():
    original = PipelineConfiguration()
    data = {"kind": "ibm_java", "primary_source_content": "class Example {}"}
    for values in ({"model_base_url": "https://example.invalid"},
                   {"approved_maven_repository_urls": ["https://repository.invalid"]}):
        changed = original.model_copy(update=values)
        assert conversion_hash(data, changed) != conversion_hash(data, original)
        assert generation_settings_identity(changed) != generation_settings_identity(original)


def test_pipeline_passes_resolved_settings_to_run_config(tmp_path, monkeypatch):
    from runtime import pipeline_runner

    profile = PipelineConfiguration(output_root=str(tmp_path), max_agent_task_retries=7,
        max_parallel_conversion_workers=3, max_parallel_llm_tasks=1,
        max_parallel_build_tasks=5, max_operations_per_batch=2,
        inter_batch_delay_secs=0, auto_rerun_impacted_operations=False,
        model_name="selected-model", model_base_url="https://model.invalid")
    captured = {}

    class StopBeforeIntake(Exception):
        pass

    def capture(settings, run_id):
        captured["config"] = create_run_config(settings, run_id)
        raise StopBeforeIntake

    monkeypatch.setattr(pipeline_runner, "create_run_config", capture)
    with pytest.raises(StopBeforeIntake):
        pipeline_runner.run_pipeline(profile, "test-run")
    config = captured["config"]
    assert config.max_agent_task_retries == 7
    assert config.max_parallel_conversion_workers == 3
    assert config.max_parallel_llm_tasks == 1
    assert config.max_parallel_build_tasks == 5
    assert config.max_operations_per_batch == 2
    assert config.inter_batch_delay_secs == 0
    assert config.auto_rerun_impacted_operations is False
    assert config.model_name == "selected-model"
    assert config.model_base_url == "https://model.invalid"


def test_effective_settings_are_saved_without_process_credentials(tmp_path, monkeypatch):
    import json
    from tools.state_store_tools.db import create_all_tables, get_connection
    from tools.state_store_tools.runs import get_run
    from tools.workspace_intake_tools.run_factory import persist_run_config
    from runtime.workspace_paths import run_report_path

    monkeypatch.setenv("GOOGLE_API_KEY", "test-secret")
    config = create_run_config(load_env_with_fallbacks(), "test-run")
    config.max_agent_task_retries = 7
    config.inter_batch_delay_secs = 0
    conn = get_connection(str(tmp_path / "state.db"))
    try:
        create_all_tables(conn)
        persist_run_config(conn, config, tmp_path)
        saved = get_run(conn, "test-run")["run_config_json"]
        assert saved["max_agent_task_retries"] == 7
        assert saved["inter_batch_delay_secs"] == 0
        assert "test-secret" not in json.dumps(saved)
        assert json.loads(run_report_path(tmp_path, "run_config.json").read_text()) == saved
    finally:
        conn.close()


def test_gemini_uses_configured_process_credential_without_network(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    import google.adk.agents
    import google.adk.runners
    import google.adk.sessions
    import google.genai
    from runtime.model_execution.adk_executor import AdkExecutor

    captured = {}
    monkeypatch.setenv("SNAPIR_TEST_KEY", "test-secret")

    def client(**kwargs):
        captured.update(kwargs)
        return object()

    def agent(**kwargs):
        # Access only the transient client; no model request is made.
        kwargs["model"].api_client
        return object()

    class Sessions:
        async def create_session(self, **kwargs):
            return SimpleNamespace(id="session")

    class Runner:
        def __init__(self, **kwargs):
            pass

        async def run_async(self, **kwargs):
            yield SimpleNamespace(is_final_response=lambda: True,
                                  content=SimpleNamespace(parts=[SimpleNamespace(text="done")]))

    monkeypatch.setattr(google.genai, "Client", client)
    monkeypatch.setattr(google.adk.agents, "LlmAgent", agent)
    monkeypatch.setattr(google.adk.sessions, "InMemorySessionService", Sessions)
    monkeypatch.setattr(google.adk.runners, "Runner", Runner)
    profile = PipelineConfiguration(model_api_key_environment="SNAPIR_TEST_KEY",
                                    model_base_url="https://model.company.test")
    assert asyncio.run(AdkExecutor(profile)._execute("instruction", "payload")) == "done"
    assert captured["api_key"] == "test-secret"
    assert captured["http_options"].base_url == "https://model.company.test"
    assert "test-secret" not in profile.model_dump_json()


def test_deployment_defaults_preserve_explicit_empty_values():
    from agents.java_deployment_manifest.agent import build_deployment_spec

    spec = build_deployment_spec("Op", {"env_vars": {}, "health_paths": {}, "container_port": 9090},
                                 template_dir="templates", environment="test")
    assert spec.env_vars == {}
    assert spec.health_paths == {}
    assert spec.port == 9090
    assert spec.template_ref.environment == "test"


def test_saved_deployment_defaults_survive_central_changes(monkeypatch):
    profile = PipelineConfiguration()
    snapshot = profile.model_dump_json()
    monkeypatch.setattr(constants, "DEPLOYMENT_DEFAULTS", {**constants.DEPLOYMENT_DEFAULTS,
                                                         "replicas": 9, "namespace": "changed"})
    restored = PipelineConfiguration.model_validate_json(snapshot)
    assert restored.deployment_defaults == profile.deployment_defaults
    assert PipelineConfiguration().deployment_defaults.replicas == 9


def test_renderer_uses_resolved_deployment_defaults(tmp_path):
    from tools.deployment_tools.template_renderer import render_manifest
    from agents.java_deployment_manifest.agent import build_deployment_spec

    (tmp_path / "resource.yaml.j2").write_text(
        "kind: ConfigMap\nmetadata:\n  namespace: {{ defaults.namespace }}\ndata:\n  replicas: '{{ defaults.replicas }}'\n")
    profile = PipelineConfiguration(deployment_defaults={**constants.DEPLOYMENT_DEFAULTS,
                                                        "namespace": "selected", "replicas": 3})
    spec = build_deployment_spec("Op", {}, template_dir=str(tmp_path))
    output = render_manifest(str(tmp_path), spec, defaults=profile.deployment_defaults)
    rendered = yaml.safe_load(output.files["resource.yaml"])
    assert rendered["metadata"]["namespace"] == "selected"
    assert rendered["data"]["replicas"] == "3"


def test_default_target_selection_cannot_enable_unimplemented_languages(monkeypatch):
    monkeypatch.setattr(constants, "TARGET_LANGUAGES", ["nodejs"])
    with pytest.raises(ValidationError):
        PipelineConfiguration()
