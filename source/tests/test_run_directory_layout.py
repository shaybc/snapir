"""Verify intake, continuation, and CLI commands share the new run layout."""

import json
import shutil
from pathlib import Path

from cli.main import main
from runtime.checkpoints import resume_pipeline
from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.runs import get_run
from runtime.workspace_paths import run_report_path
from runtime.workflow_stages import STAGES, REPORT_FOLDERS


def test_intake_and_continuation_share_state_without_inspection_reports(tmp_path, monkeypatch, capsys):
    profile = load_configuration(str(Path(__file__).resolve().parents[2] / "configs/bank_demo.yaml"))
    profile.output_root = str(tmp_path)
    profile.model_provider = "mock"
    profile.maven_settings_path = None
    directory = run_pipeline(profile, "run-layout")
    assert {path.name for path in directory.iterdir()} == {"state", "reports", "logs", "vault", "generated"}
    assert {path.name for path in (directory / "state").iterdir()} == {"migration.db", "profile.json"}
    assert {path.name for path in (directory / "reports").iterdir()} == set(REPORT_FOLDERS.values())
    assert {path.name for path in (directory / "reports" / "1_intake_and_legacy_analysis").iterdir()} == {
        "run_config.json", "component_inventory.json", "component_usage.json",
        "configured_component_usage.json", "java_source_index.json", "java_classpath_index.json",
        "java_source_dependencies.json",
    }
    assert (directory / "logs" / "mapper.log").is_file()
    assert not list((directory / "generated").iterdir())
    conn = get_connection(str(directory / "state" / "migration.db"))
    try:
        config = get_run(conn, "run-layout")["run_config_json"]
        assert config == json.loads(run_report_path(directory, "run_config.json").read_text())
        assert config["db_path"] == str(directory / "state" / "migration.db")
        assert config["output_root"] == str(directory / "generated")
        assert config["vault_root"] == str(directory / "vault")
    finally:
        conn.close()
    monkeypatch.setattr("cli.main.load_configuration", lambda _: profile)
    arguments = ["--config", "unused", "--run-id", "run-layout"]
    assert main(["status", *arguments]) == 0
    assert "planning_inputs_ready" in capsys.readouterr().out
    shutil.rmtree(directory / "reports")
    assert resume_pipeline(str(tmp_path), "run-layout") == directory
    assert run_report_path(directory, "gate_1_report.md").is_file()
    assert main(["reject", *arguments, "--gate", "1"]) == 0
    assert main(["approve", *arguments, "--gate", "1"]) == 0
    assert resume_pipeline(str(tmp_path), "run-layout") == directory
    assert run_report_path(directory, "java_classpath_index.json").is_file()
    assert run_report_path(directory, "dependency_closure.json").is_file()
    assert (directory / "vault").is_dir()
    assert main(["status", *arguments]) == 0
    status = capsys.readouterr().out
    assert "closures_blocked" in status or "conversion_pending" in status
