"""Verify local setup checks without clients, network calls, or real migrations."""

from types import SimpleNamespace

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.readiness import model_readiness_issues, intake_model_warning


@pytest.fixture(autouse=True)
def clean_model_environment(monkeypatch):
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "TEST_MODEL_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("provider,model,endpoint", [
    ("gemini", "", ""), ("gemini", "gemini/test", ""),
    ("litellm", "enterprise/model", ""),
    ("litellm", "enterprise/model", "https://example.com/v1"),
    ("litellm", "enterprise/model", "not-a-url"),
])
def test_incomplete_setup_has_actionable_intake_warning(provider, model, endpoint):
    profile = PipelineConfiguration(model_provider=provider, model_name=model, model_base_url=endpoint)
    warning = intake_model_warning(profile)
    assert "Intake may continue" in warning
    assert "planning is unavailable" in warning
    assert "process environment" in warning and "not in constants.py or YAML" in warning


@pytest.mark.parametrize("variable", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
@pytest.mark.parametrize("configured", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
def test_gemini_standard_keys_and_default_endpoint(variable, configured, monkeypatch):
    monkeypatch.setenv(variable, "test-value-never-display")
    profile = PipelineConfiguration(model_api_key_environment=configured, model_base_url="")
    assert model_readiness_issues(profile) == []


def test_vertex_and_mock_do_not_require_api_keys(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    assert model_readiness_issues(PipelineConfiguration()) == []
    assert model_readiness_issues(PipelineConfiguration(model_provider="mock", model_name="", model_base_url="dummy")) == []


def test_enterprise_requires_selected_variable_and_endpoint(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "unrelated")
    profile = PipelineConfiguration(model_provider="litellm", model_base_url="https://models.company.test/v1",
                                    model_api_key_environment="TEST_MODEL_KEY")
    assert "TEST_MODEL_KEY" in " ".join(model_readiness_issues(profile))
    monkeypatch.setenv("TEST_MODEL_KEY", "secret-test-value")
    assert model_readiness_issues(profile) == []
    profile.model_name = ""
    assert "secret-test-value" not in intake_model_warning(profile)


def test_missing_key_precedes_event_loop_and_client_construction(monkeypatch):
    monkeypatch.setattr("runtime.model_execution.adk_executor.asyncio.run", lambda *_: pytest.fail("Started event loop"))
    executor = AdkExecutor(PipelineConfiguration())
    monkeypatch.setattr(executor, "_execute", lambda *_: pytest.fail("Constructed client"))
    with pytest.raises(ValueError, match="process environment"):
        executor.execute("instruction", "payload")


def test_intake_warning_does_not_block_offline_stages(tmp_path, monkeypatch, capsys):
    from runtime.pipeline_runner import run_pipeline
    import runtime.pipeline_runner as pipeline
    empty = SimpleNamespace(issues=[], model_dump_json=lambda **_: "{}")
    inventory = SimpleNamespace(java_dependencies=empty, model_dump_json=lambda **_: "{}")
    monkeypatch.setattr(pipeline, "create_run_config", lambda *_: SimpleNamespace())
    monkeypatch.setattr(pipeline, "persist_run_config", lambda *_: None)
    monkeypatch.setattr(pipeline, "discover_java_sources", lambda *_: empty)
    monkeypatch.setattr(pipeline, "discover_java_classpath", lambda *_: empty)
    monkeypatch.setattr("tools.component_inventory_tools.build_component_inventory", lambda *_: inventory)
    monkeypatch.setattr("tools.state_store_tools.component_inventory.persist_component_inventory", lambda *_: None)
    monkeypatch.setattr("tools.state_store_tools.component_inventory.get_implementation_usage", lambda *_: [])
    monkeypatch.setattr("tools.state_store_tools.component_inventory.get_configured_component_usage", lambda *_: [])
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *_ , **__: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(pipeline, "run_legacy_composer_analysis", lambda *_: {"paused": True})
    monkeypatch.setattr(pipeline, "update_run_status", lambda *_: None)
    directory = run_pipeline(PipelineConfiguration(output_root=str(tmp_path)), "offline")
    assert directory == tmp_path / "offline"
    assert "Intake may continue" in capsys.readouterr().out


@pytest.mark.parametrize("interactive", [False, True])
@pytest.mark.parametrize("verbose", [False, True])
def test_resume_preflight_preserves_status_and_menu(tmp_path, monkeypatch, capsys, interactive, verbose):
    from cli.main import main
    from tests.test_migration_planning import run_config
    from tools.state_store_tools.db import create_all_tables, get_connection
    from tools.state_store_tools.runs import get_run, upsert_run

    state = tmp_path / "run-1" / "state"
    state.mkdir(parents=True)
    profile = PipelineConfiguration(output_root=str(tmp_path))
    (state / "profile.json").write_text(profile.model_dump_json())
    database = state / "migration.db"
    conn = get_connection(str(database))
    create_all_tables(conn)
    upsert_run(conn, run_id="run-1", run_mode="single_channel", current_phase="planning_inputs_ready",
               run_config=run_config())
    conn.close()
    monkeypatch.setattr("runtime.checkpoints.get_operations_for_planning", lambda *_: [{"operation_id": "Op", "channel": "INTERNET"}])
    monkeypatch.setattr("runtime.model_execution.adk_executor.asyncio.run", lambda *_: pytest.fail("Constructed SDK client"))
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: profile)
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: None)
    commands = iter(["resume", "exit"])
    def complete(args, _):
        if interactive:
            args.command = next(commands)
    monkeypatch.setattr("cli.main.complete_arguments", complete)
    monkeypatch.setattr("cli.main.select_resume_run", lambda: state.parent)
    monkeypatch.setattr("cli.main.clear_screen", lambda: None)
    arguments = [] if interactive else ["resume", "--config", "unused", "--run-id", "run-1"]
    assert main(arguments + (["--verbose"] if verbose else [])) == (0 if interactive else 1)
    output = capsys.readouterr()
    assert "Migration error: Model setup incomplete:" in output.out
    assert "process environment" in output.out
    assert ("Traceback" in output.err) == verbose
    assert "Unhandled exception" not in output.out + output.err
    conn = get_connection(str(database))
    run = get_run(conn, "run-1")
    assert (run["status"], run["current_phase"]) == ("failed", "planning_failed")
    conn.close()


def test_interactive_start_keeps_warning_after_clear(tmp_path, monkeypatch, capsys):
    from cli.main import main
    profile = PipelineConfiguration(output_root=str(tmp_path))
    commands = iter(["start", "exit"])
    def complete(args, _):
        args.command = next(commands)
        args.config = "unused"
    monkeypatch.setattr("cli.main.complete_arguments", complete)
    monkeypatch.setattr("cli.main.complete_run_selection", lambda *_: None)
    monkeypatch.setattr("cli.main.load_configuration", lambda *_: profile)
    monkeypatch.setattr("cli.main.run_pipeline", lambda *_: tmp_path)
    monkeypatch.setattr("cli.main.clear_screen", lambda: capsys.readouterr())
    assert main([]) == 0
    assert "Intake may continue" in capsys.readouterr().out


def test_saved_plan_resume_remains_available_without_credentials(tmp_path, monkeypatch):
    from agents.migration_planning.agent import get_operations_for_planning
    from runtime.checkpoints import resume_pipeline
    from runtime.planning import prepare_plan
    from tests.test_migration_planning import run_config, seed_operations
    from tools.state_store_tools.db import create_all_tables, get_connection
    from tools.state_store_tools.runs import get_run, upsert_run

    state = tmp_path / "run-1" / "state"
    state.mkdir(parents=True)
    profile = PipelineConfiguration(output_root=str(tmp_path), model_provider="mock")
    conn = get_connection(str(state / "migration.db"))
    create_all_tables(conn)
    config = run_config()
    upsert_run(conn, run_id="run-1", run_mode="single_channel", current_phase="gate_1_pending", run_config=config)
    seed_operations(conn, ["OpA"])
    operations = get_operations_for_planning(conn, "run-1")
    prepare_plan(conn, config, profile, operations)
    conn.close()
    profile.model_provider = "gemini"
    (state / "profile.json").write_text(profile.model_dump_json())
    monkeypatch.setattr("runtime.checkpoints.get_operations_for_planning", lambda *_: operations)
    monkeypatch.setattr("tools.component_inventory_tools.library_planner.prepare_library_plan", lambda *_: None)
    monkeypatch.setattr(AdkExecutor, "execute", lambda *_: pytest.fail("Required credentials for saved plan"))
    assert resume_pipeline(str(tmp_path), "run-1") == state.parent
    conn = get_connection(str(state / "migration.db"))
    assert get_run(conn, "run-1")["current_phase"] == "gate_1_pending"
    conn.close()


def test_conversion_enqueue_failure_marks_run_failed(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from agents.migration_planning.agent import get_operations_for_planning
    from runtime.checkpoints import resume_pipeline
    from runtime.planning import prepare_plan
    from tests.test_migration_planning import run_config, seed_operations
    from tools.state_store_tools.db import create_all_tables, get_connection
    from tools.state_store_tools.runs import get_run, upsert_run

    state = tmp_path / "run-1" / "state"
    state.mkdir(parents=True)
    profile = PipelineConfiguration(output_root=str(tmp_path), model_provider="mock")
    conn = get_connection(str(state / "migration.db"))
    create_all_tables(conn)
    config = run_config()
    upsert_run(conn, run_id="run-1", run_mode="single_channel", current_phase="conversion_pending", run_config=config)
    seed_operations(conn, ["OpA"])
    prepare_plan(conn, config, profile, get_operations_for_planning(conn, "run-1"))
    conn.close()
    (state / "profile.json").write_text(profile.model_dump_json())
    monkeypatch.setattr("runtime.checkpoints.java_scope", lambda *_: nullcontext())
    monkeypatch.setattr("tools.component_inventory_tools.library_planner.prepare_library_plan", lambda *_: None)
    monkeypatch.setattr("runtime.checkpoints.evaluate_gate", lambda *_: "approved")
    monkeypatch.setattr("runtime.checkpoints.discover_java_classpath", lambda *_: SimpleNamespace(model_dump_json=lambda **_: "{}"))
    monkeypatch.setattr("runtime.checkpoints.resolve_context_fields", lambda *_: None)
    monkeypatch.setattr("runtime.checkpoints.build_operation_closure", lambda *_ , **__: SimpleNamespace(model_dump=lambda **_: {"status": "READY"}))
    def fail(*_):
        raise ValueError("Component is outside the reviewed library plan: Example")
    monkeypatch.setattr("runtime.managed_projects.enqueue_closure_conversions", fail)
    with pytest.raises(ValueError, match="outside the reviewed library plan"):
        resume_pipeline(str(tmp_path), "run-1")
    conn = get_connection(str(state / "migration.db"))
    saved = get_run(conn, "run-1")
    assert saved["status"] == "failed"
    assert saved["current_phase"] == "conversion_pending"
    conn.close()
