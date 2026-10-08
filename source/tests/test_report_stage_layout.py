"""Verify stage paths, Markdown relocation and preserved matching approvals."""

import hashlib
import json
import re
import sqlite3

import pytest

from runtime.gate_one_reports import read_gate_one_reports
from runtime.human_gates import record_decision, evaluate_gate
from runtime.report_layout_migration import migrate_report_layout, _old_gate_one_bundle, number_report_folders
from runtime.workspace_paths import run_report_path
from runtime.workflow_stages import STAGES, REPORT_FOLDERS, workflow_stage_label
from tests.test_gate_one_report_bundle import create_bundle


def legacy_bundle(directory):
    conn, _ = create_bundle(directory)
    conn.close()
    stage = directory / "reports/2_migration_planning"
    overview = stage / "gate_1_report.md"
    (directory / "gate_1_report.md").write_text(overview.read_text().replace("(gate_1/", "(reports/gate_1/"))
    overview.unlink()
    (stage / "gate_1").rename(directory / "reports/gate_1")
    old = directory / "reports/gate_1"
    manifest = old / "manifest.json"
    paths = json.loads(manifest.read_text())
    manifest.write_text(json.dumps([path.replace("reports/2_migration_planning/gate_1/", "reports/gate_1/") for path in paths]))
    for operation in (old / "operations").glob("*.md"):
        operation.write_text(operation.read_text().replace("(../../gate_1_report.md)", "(../../../gate_1_report.md)"))
    shared = old / "shared_libraries.md"
    shared.write_text(shared.read_text().replace("(../gate_1_report.md)", "(../../gate_1_report.md)"))
    return _old_gate_one_bundle(directory)


def test_moves_reports_fixes_links_and_preserves_existing_approval(tmp_path):
    directory = tmp_path / "run-1"
    old_hash = legacy_bundle(directory)
    (directory / "closures.json").write_text("[]")
    (directory / "reports/component_inventory.json").write_text("{}")
    state = directory / "state"
    state.mkdir()
    with sqlite3.connect(state / "migration.db") as conn:
        conn.execute("CREATE TABLE runtime_gate_decisions(run_id,gate_number,report_hash,decision,policy,decided_at,PRIMARY KEY(run_id,gate_number,report_hash))")
        conn.execute("INSERT INTO runtime_gate_decisions VALUES('run-1',1,?,'approved','human','original-time')", (old_hash,))
    moved = migrate_report_layout(directory)
    assert len(moved) == 4
    assert {path.name for path in (directory / "reports").iterdir()} == set(REPORT_FOLDERS.values())
    assert not (directory / "closures.json").exists()
    assert run_report_path(directory, "dependency_closure.json").read_text() == "[]"
    for report in (directory / "reports").rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", report.read_text()):
            assert (report.parent / link).resolve().is_file()
    new_bundle = read_gate_one_reports(directory)
    with sqlite3.connect(state / "migration.db") as conn:
        assert evaluate_gate(conn, "run-1", 1, new_bundle, "human", True) == "approved"
        assert conn.execute("SELECT COUNT(*) FROM runtime_gate_decisions WHERE decided_at='original-time'").fetchone()[0] == 2
    assert migrate_report_layout(directory) == []


def test_collision_leaves_original_report_untouched(tmp_path):
    (tmp_path / "closures.json").write_text("original")
    path = run_report_path(tmp_path, "dependency_closure.json")
    path.parent.mkdir(parents=True)
    path.write_text("existing")
    with pytest.raises(ValueError, match="already exists"):
        migrate_report_layout(tmp_path)
    assert (tmp_path / "closures.json").read_text() == "original"


def test_numbered_folders_preserve_links_and_matching_approval(tmp_path):
    directory = tmp_path / "run-1"
    conn, _ = create_bundle(directory)
    conn.close()
    reports = directory / "reports"
    for stage, folder in REPORT_FOLDERS.items():
        (reports / folder).mkdir(exist_ok=True)
        (reports / folder).rename(reports / stage)
    manifest = reports / "migration_planning/gate_1/manifest.json"
    paths = [path.replace("reports/2_migration_planning/", "reports/migration_planning/") for path in json.loads(manifest.read_text())]
    manifest.write_text(json.dumps(paths))
    contents = {"reports/migration_planning/gate_1_report.md": (reports / "migration_planning/gate_1_report.md").read_text(encoding="utf-8")}
    contents.update({path: (directory / path).read_text(encoding="utf-8") for path in paths})
    old_hash = hashlib.sha256(json.dumps(contents, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    (directory / "state").mkdir()
    with sqlite3.connect(directory / "state/migration.db") as conn:
        conn.execute("CREATE TABLE runtime_gate_decisions(run_id,gate_number,report_hash,decision,policy,decided_at,PRIMARY KEY(run_id,gate_number,report_hash))")
        conn.execute("INSERT INTO runtime_gate_decisions VALUES('run-1',1,?,'approved','human','original-time')", (old_hash,))
    assert number_report_folders(directory) == list(REPORT_FOLDERS.values())
    assert sorted(path.name for path in reports.iterdir()) == list(REPORT_FOLDERS.values())
    for report in reports.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", report.read_text()):
            assert (report.parent / link).resolve().is_file()
    with sqlite3.connect(directory / "state/migration.db") as conn:
        assert evaluate_gate(conn, "run-1", 1, read_gate_one_reports(directory), "human", True) == "approved"
    assert number_report_folders(directory) == []


@pytest.mark.parametrize("phase,label", [
    ("mapper", "Intake and legacy analysis"), ("gate_1_pending", "Migration planning"),
    ("closures_blocked", "Dependency closure and component conversion"),
    ("gate_2_pending", "Component review"), ("gate_3_pending", "Operation assembly and review"),
    ("service_generation", "Service generation and validation"), ("gate_4_pending", "Final validation"),
])
def test_checkpoint_labels_follow_readme_stages(phase, label):
    assert workflow_stage_label(phase) == label
