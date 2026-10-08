"""Verify operation review, durable revisions, and evidence-bound Gate 3."""

from runtime.workspace_paths import run_report_path, write_run_report
import json
from pathlib import Path

from models.maven_dependency import JavaConversionOutput
from runtime.operation_assembly import run_operation_assembly
from runtime.operation_review import run_operation_review_gate
from runtime.human_gates import record_decision
from tests.runtime.test_operation_assembly import assembly_setup, skeleton
from tools.state_store_tools.agent_tasks import upsert_agent_task
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
from agents.operation_assembly.step_implementation_inserter.agent import replace_method_body
from runtime.operation_assembly.generation import make_pass_generator


def setup_review(tmp_path, policy="human"):
    setup, plans, factory, component_gate = assembly_setup(tmp_path)
    conn, config, profile, plan, _ = setup
    profile.gate_policies["3"] = policy
    dto = tmp_path / "generated/INTERNET/Op/src/main/java/org/example/OpResponse.java"
    dto.parent.mkdir(parents=True, exist_ok=True)
    dto.write_text("package org.example; public class OpResponse {}")
    data = dict(conversion_id="ReplyFmt", kind="xml_fmtdef", channel="INTERNET", primary_source_content="<fmtDef/>",
                relationship_context="reply", target_kind="native_java", managed_project_operation="Op")
    upsert_agent_task(conn, task_id="reply", run_id=config.run_id, agent_name="ManagedConversion", scope_type="java_class",
                      scope_id="ReplyFmt", channel="INTERNET", target_language="java", status="completed", input_data=data)
    upsert_native_java_artifact(conn, artifact_id="run-1:native_java:reply", run_id=config.run_id, conversion_id="ReplyFmt",
                                kind="xml_fmtdef", logical_id="ReplyFmt", artifact_path=str(dto), compiles=True, status="converted")
    closure = json.loads(conn.execute("SELECT closure_json FROM operation_closures").fetchone()[0])
    closure["ref_formats"] = {"csReplyFormat": "ReplyFmt"}
    conn.execute("UPDATE operation_closures SET closure_json=?", (json.dumps(closure),))
    conn.commit()
    def model(instruction, payload):
        request = json.loads(payload)
        name = request["method_name"]
        body = ["return;"] if name in {"initializeContext", "enrichWithDbLookups"} else ["return null;"]
        if name == "execute":
            body.insert(0, "var ctx = new Object();")
            if request.get("equivalence_feedback"):
                body.insert(0, "// fixed")
        return json.dumps(dict(java_source=replace_method_body(request["current_class"], name, body), dependencies=[]))
    def assemble():
        return run_operation_assembly(conn, config, profile, plan, tmp_path, gate_checker=component_gate,
            plan_builder=plans, context_factory=factory,
            skeleton_generator=lambda profile, payload: JavaConversionOutput(java_source=skeleton().replace("public Object execute", "public OpResponse execute")),
            pass_factory=lambda profile, payload, context: make_pass_generator(profile, payload, context, model))
    assert assemble() == "operation_review_pending"
    return setup, component_gate, assemble


def approved(item):
    return dict(operation_id=item["operation_id"], confidence="high", review_status="approved")


def invoke(tmp_path, setup, component_gate, assemble, reviewer=approved):
    conn, config, profile, plan, _ = setup
    return run_operation_review_gate(conn, config, profile, plan, tmp_path, model_reviewer=reviewer,
                                      component_gate=component_gate, project_builder=lambda path: True, assembly_runner=assemble)


def test_gate3_requires_approval_and_caches_unchanged_review(tmp_path):
    setup, gate, assemble = setup_review(tmp_path)
    calls = []
    reviewer = lambda item: calls.append(item["original_xml"]) or approved(item)
    assert invoke(tmp_path, setup, gate, assemble, reviewer) == "gate_3_pending"
    record_decision(setup[0], "run-1", 3, run_report_path(tmp_path, "gate_3_report.txt").read_text(), "approved")
    assert invoke(tmp_path, setup, gate, assemble, reviewer) == "service_generation_pending"
    assert calls == ["<operation/>"]


def test_gate3_uses_actual_approved_reply_type(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    dto = tmp_path / "generated/INTERNET/Op/src/main/java/org/example/OpResponse.java"
    dto.write_text("package org.example; public class ClientReply {}")
    # A successful rebuilt fixture records the new component and return signature.
    conn = setup[0]
    renamed = dto.with_name("ClientReply.java")
    dto.rename(renamed)
    conn.execute("UPDATE native_java_artifacts SET artifact_path=? WHERE artifact_id='run-1:native_java:reply'", (str(renamed),))
    path = Path(conn.execute("SELECT service_path FROM operation_assembly_snapshots").fetchone()[0])
    path.write_text(path.read_text().replace("public OpResponse execute", "public ClientReply execute"))
    import hashlib
    conn.execute("UPDATE operation_assembly_snapshots SET service_hash=?", (hashlib.sha256(path.read_bytes()).hexdigest(),))
    conn.commit()
    assert invoke(tmp_path, setup, gate, assemble) == "service_generation_pending"


def test_stale_xml_blocks_even_skip_policy(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "skip")
    (tmp_path / "operation.xml").write_text("<operation changed='true'/>")
    assert invoke(tmp_path, setup, gate, assemble) == "operation_review_blocked"


def test_low_confidence_cannot_auto_approve(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    reviewer = lambda item: dict(operation_id="Op", confidence="low", review_status="approved")
    assert invoke(tmp_path, setup, gate, assemble, reviewer) == "operation_review_blocked"


def test_review_feedback_reassembles_and_passes(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    def reviewer(item):
        if "fixed" in item["java_source"]:
            return approved(item)
        return dict(operation_id="Op", logic_differences=["Fix serializer"], confidence="medium", review_status="needs_revision")
    assert invoke(tmp_path, setup, gate, assemble, reviewer) == "service_generation_pending"
    assert setup[0].execute("SELECT attempts FROM operation_revision_attempts").fetchone()[0] == 1


def test_revision_budget_survives_resume(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    calls = []
    def revise():
        calls.append(True)
        return assemble()
    reviewer = lambda item: dict(operation_id="Op", logic_differences=["Unresolved logic"], confidence="medium", review_status="needs_revision")
    assert invoke(tmp_path, setup, gate, revise, reviewer) == "operation_review_blocked"
    assert len(calls) == setup[1].max_agent_task_retries
    assert invoke(tmp_path, setup, gate, revise, reviewer) == "operation_review_blocked"
    assert len(calls) == setup[1].max_agent_task_retries


def test_gate3_rejection_remains_effective(tmp_path):
    setup, gate, assemble = setup_review(tmp_path)
    assert invoke(tmp_path, setup, gate, assemble) == "gate_3_pending"
    record_decision(setup[0], "run-1", 3, run_report_path(tmp_path, "gate_3_report.txt").read_text(), "rejected")
    assert invoke(tmp_path, setup, gate, assemble) == "gate_3_rejected"


def test_successful_reassembly_invalidates_previous_gate3_approval(tmp_path):
    setup, gate, assemble = setup_review(tmp_path)
    assert invoke(tmp_path, setup, gate, assemble) == "gate_3_pending"
    record_decision(setup[0], "run-1", 3, run_report_path(tmp_path, "gate_3_report.txt").read_text(), "approved")
    (tmp_path / "operation.xml").write_text("<operation updated='true'/>")
    assert assemble() == "operation_review_pending"
    assert invoke(tmp_path, setup, gate, assemble) == "gate_3_pending"


def test_model_approval_cannot_override_structural_failure(tmp_path):
    setup, gate, assemble = setup_review(tmp_path, "automatic")
    conn = setup[0]
    source = Path(conn.execute("SELECT service_path FROM operation_assembly_snapshots").fetchone()[0])
    source.write_text(source.read_text().replace("var ctx = new Object();", ""))
    import hashlib
    conn.execute("UPDATE operation_assembly_snapshots SET service_hash=?", (hashlib.sha256(source.read_bytes()).hexdigest(),))
    conn.commit()
    assert invoke(tmp_path, setup, gate, lambda: "assembly_blocked") == "operation_review_blocked"


def test_review_updates_do_not_touch_other_channel_artifacts(tmp_path):
    setup, gate, assemble = setup_review(tmp_path)
    conn = setup[0]
    upsert_native_java_artifact(conn, artifact_id="ivr-assembly", run_id="run-1", conversion_id="Op",
                                kind="xml_operation", logical_id="Op", review_status="pending", status="converted",
                                artifact_path=str(tmp_path / "generated/IVR/Op/src/main/java/OpService.java"))
    assert invoke(tmp_path, setup, gate, assemble) == "gate_3_pending"
    assert conn.execute("SELECT review_status FROM native_java_artifacts WHERE artifact_id='ivr-assembly'").fetchone()[0] == "pending"
