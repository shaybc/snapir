"""Verify linked Gate One documents and approval binding across their contents."""

from runtime.workspace_paths import run_report_path, write_run_report
import json
import re

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.gate_one_reports import write_gate_one_reports, read_gate_one_reports
from runtime.human_gates import record_decision, evaluate_gate
from tests.test_migration_planning import memory_conn, run_config, plan, batch, packet


def create_bundle(directory):
    conn = memory_conn()
    proposal = plan([batch("batch-1", [packet("OpA"), packet("OpB")], is_pilot=True)])
    operations = [{"channel": "INTERNET", "operation_id": name, "shared_formats_count": 0,
                   "has_blocked_context": False} for name in ("OpA", "OpB")]
    report = write_gate_one_reports(directory, conn, run_config(), PipelineConfiguration(), proposal, operations, None)
    return conn, report


def test_overview_links_to_separate_operation_and_library_reports(tmp_path):
    conn, report = create_bundle(tmp_path)
    summary = run_report_path(tmp_path, "gate_1_report.md").read_text(encoding="utf-8")
    assert "INTERNET / OpA" in summary and "INTERNET / OpB" in summary
    assert "RECORDED LEGACY STEPS" not in summary
    paths = json.loads((tmp_path / "reports/2_migration_planning/gate_1/manifest.json").read_text())
    assert len(paths) == 3
    for link in re.findall(r"\]\(([^)]+)\)", summary):
        assert (run_report_path(tmp_path, "gate_1_report.md").parent / link).is_file()
    first = (tmp_path / paths[0]).read_text()
    assert "INTERNET / OpA" in first and "INTERNET / OpB" not in first
    assert "RECORDED LEGACY STEPS" in first
    assert report == read_gate_one_reports(tmp_path)
    conn.close()


def test_changed_operation_report_invalidates_approval(tmp_path):
    conn, report = create_bundle(tmp_path)
    record_decision(conn, "run-1", 1, report, "approved")
    assert evaluate_gate(conn, "run-1", 1, read_gate_one_reports(tmp_path), "human", True) == "approved"
    paths = json.loads((tmp_path / "reports/2_migration_planning/gate_1/manifest.json").read_text())
    operation = tmp_path / paths[0]
    operation.write_text(operation.read_text() + "\nChanged review evidence\n")
    assert evaluate_gate(conn, "run-1", 1, read_gate_one_reports(tmp_path), "human", True) == "pending"
    conn.close()


def test_missing_linked_report_prevents_approval_read(tmp_path):
    conn, _ = create_bundle(tmp_path)
    paths = json.loads((tmp_path / "reports/2_migration_planning/gate_1/manifest.json").read_text())
    (tmp_path / paths[0]).unlink()
    with pytest.raises(FileNotFoundError):
        read_gate_one_reports(tmp_path)
    conn.close()
