"""Verify actionable interactive progress without changing saved runs."""

import json
import sqlite3
import pytest

from cli.workflow_progress import display_workflow_progress
from runtime.workspace_paths import run_report_path
from runtime.human_gates import record_decision


def make_run(tmp_path, phase, status="paused", profile=None):
    directory = tmp_path / "run-example"
    state = directory / "state"
    state.mkdir(parents=True)
    (state / "profile.json").write_text(json.dumps(profile or {}), encoding="utf-8")
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT, current_phase TEXT)")
        conn.execute("INSERT INTO runs VALUES (?, ?, ?)", (directory.name, status, phase))
    return directory


@pytest.mark.parametrize('decision,changed,advances', [('approved', False, True), ('rejected', False, False), ('approved', True, False)])
def test_gate_three_moves_display_only_after_current_report_approval(tmp_path, capsys, decision, changed, advances):
    directory = make_run(tmp_path, 'gate_3_pending')
    report = run_report_path(directory, 'gate_3_report.txt')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('Current operation review', encoding='utf-8')
    database = directory / 'state/migration.db'
    with sqlite3.connect(database) as conn:
        record_decision(conn, directory.name, 3, report.read_text(), decision)
    if changed:
        report.write_text('Changed operation review', encoding='utf-8')
    before = database.read_bytes()
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    if advances:
        assert '[V] 5. Operation assembly and review (COMPLETED)' in text
        assert '→ 6. Service generation and validation (WAITING FOR RESUME)' in text
        assert 'Approve operation' not in text
        assert 'checkpoint detail unavailable' not in text
        assert 'Resume this run to start service generation' in text
    else:
        assert '→ 5. Operation assembly and review (WAITING)' in text
        assert '[ ] 6. Service generation and validation (PENDING)' in text
    assert database.read_bytes() == before


def test_conversion_guidance_preserves_state(tmp_path, capsys):
    directory = make_run(tmp_path, "conversion_pending")
    database = directory / "state" / "migration.db"
    before = database.read_bytes()
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    assert "[V] 1. Intake and legacy analysis (COMPLETED)" in text
    assert "[V] 2. Migration planning (COMPLETED)" in text
    assert "→ 3. Dependency closure and component conversion (WAITING)" in text
    assert "[ ] 4. Component review (PENDING)" in text
    assert "requires a configured Maven settings file" not in text
    assert "Resume this run to start component conversion" in text
    assert database.read_bytes() == before


def test_configured_maven_does_not_claim_missing_settings(tmp_path, capsys):
    directory = make_run(tmp_path, "conversion_pending", profile={"maven_settings_path": "settings.xml"})
    display_workflow_progress(directory)
    text = capsys.readouterr().out
    assert "requires a configured Maven" not in text
    assert "ready for component conversion" in text


def test_behavior_unit_failure_guidance_uses_saved_strategy(tmp_path, capsys):
    directory = make_run(tmp_path, "conversion_pending", "failed", profile={"conversion_strategy": "behavior_units"})
    before = (directory / "state/migration.db").read_bytes()
    display_workflow_progress(directory)
    assert "Native behavior-unit conversion failed" in capsys.readouterr().out
    assert (directory / "state/migration.db").read_bytes() == before


def test_blocked_dependencies_and_future_stages(tmp_path, capsys):
    display_workflow_progress(make_run(tmp_path, "closures_blocked", "blocked"))
    text = capsys.readouterr().out
    assert "! 3. Dependency closure and component conversion (BLOCKED)" in text
    assert "resolve its blocking issues" in text
    assert "[ ] 7. Final validation (PENDING)" in text


def test_final_completion_marks_all_stages_complete(tmp_path, capsys):
    display_workflow_progress(make_run(tmp_path, "migration_approved", "completed"))
    text = capsys.readouterr().out
    assert "[V] 7. Final validation (COMPLETED)" in text
    assert "(PENDING)" not in text


def test_legacy_console_uses_readable_markers(tmp_path, monkeypatch):
    import io
    from cli import workflow_progress
    output = io.BytesIO()
    console = io.TextIOWrapper(output, encoding="ascii")
    monkeypatch.setattr(workflow_progress.sys, "stdout", console)
    display_workflow_progress(make_run(tmp_path, "conversion_pending"))
    console.flush()
    text = output.getvalue().decode("ascii")
    assert "[V] 1." in text
    assert "-> 3." in text


def test_failed_conversion_is_not_displayed_as_waiting(tmp_path, capsys):
    display_workflow_progress(make_run(tmp_path, "conversion_pending", "failed"))
    text = capsys.readouterr().out
    assert "! 3. Dependency closure and component conversion (FAILED)" in text
    assert "Component conversion failed" in text
    assert "(WAITING)" not in text


def test_intake_review_is_optional_before_planning(tmp_path, capsys):
    display_workflow_progress(make_run(tmp_path, "planning_inputs_ready"))
    text = capsys.readouterr().out
    assert "2. Migration planning (READY TO START)" in text
    assert "Optionally review the intake reports" in text
    assert "1_intake_and_legacy_analysis" in text
    assert "Resume a migration to begin migration planning" in text
