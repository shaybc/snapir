"""Verify evidence-complete, content-bound final delivery approval."""

import json
from pathlib import Path

from runtime.finalization import run_finalization
from runtime.human_gates import record_decision
from tests.runtime.test_service_generation import ready, run


def setup_final(tmp_path, complete=False):
    setup = ready(tmp_path)
    assert run(tmp_path, setup) == "validation_evidence_pending"
    conn, config, profile, plan, _ = setup
    profile.deployment_template_dir = str(Path(__file__).resolve().parents[2] / "templates/deployment")
    profile.deployment_values = {"INTERNET/Op": dict(image_name="registry.example/service:1.0.0")}
    if complete:
        row = conn.execute("SELECT validation_json FROM service_generation_checkpoints").fetchone()
        value = json.loads(row[0])
        value.update(xml_compatibility="passed", behavioral_equivalence="passed", legacy_trace_comparison="passed")
        (tmp_path / "explicit-test-evidence.txt").write_text("Explicit fixture evidence; not a real migration result.")
        value["evidence_paths"] = {name: ["explicit-test-evidence.txt"] for name in
                                  ("xml_compatibility", "behavioral_equivalence", "legacy_trace_comparison")}
        conn.execute("UPDATE service_generation_checkpoints SET validation_json=?", (json.dumps(value),))
        conn.commit()
    return setup


def finalize(tmp_path, setup):
    conn, config, profile, plan, _ = setup
    return run_finalization(conn, config, profile, plan, tmp_path)


def test_missing_behavior_evidence_blocks_even_automatic_gate(tmp_path):
    setup = setup_final(tmp_path)
    setup[2].gate_policies["4"] = "automatic"
    assert finalize(tmp_path, setup) == "finalization_blocked"
    inventory = json.loads((tmp_path / "delivery_manifest.json").read_text())
    assert not inventory["production_ready"]
    assert not inventory["deployed"]
    assert any("behavioral_equivalence" in value for value in inventory["blockers"])
    assert (tmp_path / "deliverables/INTERNET/Op/deployment/deployment.yaml").exists()


def test_human_gate4_requires_current_report_approval(tmp_path):
    setup = setup_final(tmp_path, True)
    assert finalize(tmp_path, setup) == "gate_4_pending"
    record_decision(setup[0], setup[1].run_id, 4, (tmp_path / "gate_4_report.txt").read_text(), "approved")
    assert finalize(tmp_path, setup) == "migration_approved"
    setup[2].deployment_values["INTERNET/Op"]["image_name"] = "registry.example/service:2.0.0"
    assert finalize(tmp_path, setup) == "gate_4_pending"


def test_changed_project_invalidates_final_approval(tmp_path):
    setup = setup_final(tmp_path, True)
    setup[2].gate_policies["4"] = "automatic"
    assert finalize(tmp_path, setup) == "migration_approved"
    (tmp_path / "services/INTERNET/Op/src/main/resources/application.properties").write_text("changed")
    assert finalize(tmp_path, setup) == "finalization_blocked"


def test_missing_deployment_configuration_is_explicit(tmp_path):
    setup = setup_final(tmp_path, True)
    setup[2].deployment_values = {}
    assert finalize(tmp_path, setup) == "finalization_blocked"
    assert "explicit image configuration" in (tmp_path / "final_report.md").read_text()


def test_gate4_rejection_survives_resume(tmp_path):
    setup = setup_final(tmp_path, True)
    assert finalize(tmp_path, setup) == "gate_4_pending"
    record_decision(setup[0], setup[1].run_id, 4, (tmp_path / "gate_4_report.txt").read_text(), "rejected")
    assert finalize(tmp_path, setup) == "gate_4_rejected"
