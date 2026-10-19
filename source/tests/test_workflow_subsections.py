"""Check active-only nested progress, saved failures and read-only compatibility."""

import json
import sqlite3

import pytest

from cli.workflow_progress import display_workflow_progress
from cli.workflow_subsections import active_subsections, subsection_lines
from tests.test_workflow_progress import make_run


def state(directory, attempts=(), snapshots=()):
    """Create only the optional evidence tables the display reads."""
    with sqlite3.connect(directory / "state/migration.db") as conn:
        conn.execute("CREATE TABLE behavior_attempts (run_id TEXT, category TEXT, identity TEXT, created_at TEXT, request_json TEXT, response TEXT, error TEXT)")
        conn.execute("CREATE TABLE behavior_snapshots (run_id TEXT, category TEXT, identity TEXT, status TEXT, data_json TEXT)")
        for number, (category, identity, response, error, request) in enumerate(attempts):
            conn.execute("INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?)",
                         (directory.name, category, identity, str(number), json.dumps(request), json.dumps(response) if response else None, error))
        for category, identity, status, data in snapshots:
            conn.execute("INSERT INTO behavior_snapshots VALUES (?,?,?,?,?)",
                         (directory.name, category, identity, status, json.dumps(data)))


@pytest.mark.parametrize("phase,title", [
    ("mapper", "Run mapper"), ("planning", "Create plan"), ("conversion_pending", "Convert units"),
    ("gate_2_pending", "Approve components"), ("assembly_pending", "Plan tests"),
    ("service_generation", "Generate service"), ("gate_4_pending", "Approve migration"),
])
def test_every_stage_expands_only_its_own_subsections(tmp_path, capsys, phase, title):
    directory = make_run(tmp_path, phase)
    before = (directory / "state/migration.db").read_bytes()
    display_workflow_progress(directory)
    output = capsys.readouterr().out
    assert title in output
    # Other stage subsection titles must not leak into the active stage tree.
    unique = {"mapper": "Run mapper", "planning": "Create plan", "conversion_pending": "Convert units",
              "gate_2_pending": "Approve components", "assembly_pending": "Plan tests",
              "service_generation": "Generate service", "gate_4_pending": "Approve migration"}
    for other, text in unique.items():
        if other != phase:
            assert text not in output
    assert (directory / "state/migration.db").read_bytes() == before


def test_latest_interface_failure_is_before_compile_and_tests(tmp_path, capsys):
    directory = make_run(tmp_path, "assembly_pending", "failed")
    identity = "INTERNET/TransferFundsOp"
    state(directory, attempts=[
        ("service_implementation", identity, {"files": [{"path": "src/main/java/Service.java"}, {"path": "src/test/java/Test.java"}]},
         "Provisional assembly must return main implementation files only; route tests follow separately", {}),
        ("service_implementation", identity, {"files": [{"path": "src/main/java/Service.java"}]}, "Assembly changed an accepted interface", {}),
        ("service_implementation", identity, {"files": [{"path": "src/main/java/Service.java"}]}, "Assembly changed an accepted interface", {}),
    ])
    before = (directory / "state/migration.db").read_bytes()
    display_workflow_progress(directory)
    output = capsys.readouterr().out
    assert "[V] 1. Gather" in output
    assert "[V] 2. Generate" in output
    assert "! 2. Accepted interfaces" in output
    assert "[ ] 3. Compile" in output
    assert "[ ] 4. Plan tests" in output
    assert "[ ] 5. Test scenarios" in output
    assert identity in output
    assert (directory / "state/migration.db").read_bytes() == before


def test_scenarios_preserve_accepted_and_identify_failed_test(tmp_path):
    directory = make_run(tmp_path, "assembly_pending", "failed")
    identity = "WEB/Transfer"
    state(directory, attempts=[
        ("service_implementation", identity, {"files": [{}]}, None, {}),
        ("route_scenario_test", identity + ":success", {"files": [{}]}, None, {}),
        ("route_scenario_test", identity + ":timeout", {"files": [{}]}, "Maven test: assertion failed", {"failed_test_context": {"failures": ["timeout"]}}),
    ], snapshots=[
        ("service_implementation", identity, "accepted", {}),
        ("route_test_plan", identity, "accepted", {"scenarios": [
            {"scenario_id": "success", "description": "Successful transfer"},
            {"scenario_id": "timeout", "description": "Timeout route"},
            {"scenario_id": "error", "description": "Error route"},
        ]}),
        ("route_scenario_test", identity + ":success", "accepted", {}),
    ])
    with sqlite3.connect(directory / "state/migration.db") as conn:
        nodes = active_subsections(conn, directory, "failed", "assembly_pending")
    scenarios = next(node for node in nodes if node[0] == "scenarios")
    assert [node[2] for node in scenarios[3]] == ["completed", "attention", "pending"]
    assert scenarios[3][1][3][-1][2] == "attention"
    assert scenarios[3][1][3][-2][2] == "completed"
    assert "! 4. Run test" in "\n".join(subsection_lines(nodes))


def test_failed_retry_is_not_hidden_by_old_accepted_implementation(tmp_path):
    directory = make_run(tmp_path, "assembly_pending", "failed")
    state(directory, attempts=[("service_implementation", "WEB/Transfer", {"files": [{}]}, "Assembly changed an accepted interface", {})],
          snapshots=[("service_implementation", "WEB/Transfer", "accepted", {})])
    with sqlite3.connect(directory / "state/migration.db") as conn:
        nodes = active_subsections(conn, directory, "failed", "assembly_pending")
    assert next(node for node in nodes if node[0] == "validate")[2] == "attention"


def test_old_run_does_not_claim_unrecorded_work_completed(tmp_path, capsys):
    display_workflow_progress(make_run(tmp_path, "assembly_pending", "failed"))
    output = capsys.readouterr().out
    assert "checkpoint detail unavailable" in output
    assert "[ ] 3. Compile" in output
    assert "[V] 1. Gather" not in output


def test_provider_failure_marks_generation_not_validation(tmp_path):
    directory = make_run(tmp_path, "assembly_pending", "failed")
    state(directory, attempts=[("service_implementation", "WEB/Transfer", None, "Provider unavailable", {})])
    with sqlite3.connect(directory / "state/migration.db") as conn:
        nodes = active_subsections(conn, directory, "failed", "assembly_pending")
    assert next(node for node in nodes if node[0] == "generate")[2] == "attention"
    assert next(node for node in nodes if node[0] == "validate")[2] == "pending"


def test_compile_failure_preserves_successful_interface_validation(tmp_path):
    directory = make_run(tmp_path, "assembly_pending", "failed")
    state(directory, attempts=[("service_implementation", "WEB/Transfer", {"files": [{}]}, "Maven compile: missing method", {"failed_compiler_context": {"diagnostics": ["missing method"]}})])
    with sqlite3.connect(directory / "state/migration.db") as conn:
        nodes = active_subsections(conn, directory, "failed", "assembly_pending")
    output = "\n".join(subsection_lines(nodes))
    assert "[V] 2. Accepted interfaces" in output
    assert "! 3. Compile" in output
