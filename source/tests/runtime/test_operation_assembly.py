"""Exercise assembly orchestration with explicit model and compiler fixtures."""

from runtime.workspace_paths import run_report_path, write_run_report
import json
import subprocess

from models.conversion_models import ContextPlan, RoutingPlan, SerializationPlan
from models.maven_dependency import JavaConversionOutput
from runtime.component_review import run_component_review_gate
from runtime.operation_assembly import run_operation_assembly
from runtime.operation_assembly.generation import make_pass_generator
from agents.operation_assembly.step_implementation_inserter.agent import replace_method_body
from tests.runtime.test_component_review_gate import setup_run, approved
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.state_store_tools.operation_closures import upsert_operation_closure
from tools.state_store_tools.context_plans import upsert_context_plan
from tools.state_store_tools.routing_plans import upsert_routing_plan
from tools.state_store_tools.serialization_plans import upsert_serialization_plan


def skeleton():
    stub = 'throw new UnsupportedOperationException("not yet implemented");'
    return "\n".join([
        "package org.example;", "public class OpService {",
        "public Object execute(String xml) throws Exception { " + stub + " }",
        "private Object deserializeRequest(String xml) { " + stub + " }",
        "private void initializeContext(Object ctx, Object req) { " + stub + " }",
        "private void enrichWithDbLookups(Object ctx) { " + stub + " }",
        "private String serializeReply(Object reply) { " + stub + " }",
        "private String serializeErrorReply(Object error) { " + stub + " }", "}",
    ])


def assembly_setup(tmp_path):
    setup = setup_run(tmp_path, "automatic")
    conn, config, profile, plan, _ = setup
    xml = tmp_path / "operation.xml"
    xml.write_text("<operation/>")
    upsert_operation_closure(conn, operation_id="Op", channel="INTERNET", run_id=config.run_id,
                            status="READY", closure={"source_xml_path": str(xml)})
    def plans(connection, run_config, packet):
        routing = RoutingPlan(operation_id="Op", channel="INTERNET", has_finally_step=False)
        context = ContextPlan(operation_id="Op", channel="INTERNET", context_class="Object")
        serialization = SerializationPlan(operation_id="Op", channel="INTERNET")
        for writer, value in ((upsert_routing_plan, routing), (upsert_context_plan, context), (upsert_serialization_plan, serialization)):
            writer(connection, operation_id="Op", channel="INTERNET", run_id=config.run_id,
                   plan=value.model_dump(mode="json"), status="ready")
        return routing, context, serialization
    class Verifier:
        def __call__(self, dependency):
            pass
        def compile_project(self, project, allowed=(), *, goal="compile"):
            return subprocess.CompletedProcess(["mvn"], 0, "", "")
    factory = lambda profile, project, artifact: ManagedBuildContext(str(project / "pom.xml"), Verifier())
    gate = lambda: run_component_review_gate(conn, config, profile, plan, tmp_path,
                                             model_reviewer=approved, project_builder=lambda path: True)
    return setup, plans, factory, gate


def run(tmp_path, setup, plans, factory, gate, model_call):
    conn, config, profile, plan, _ = setup
    return run_operation_assembly(conn, config, profile, plan, tmp_path, gate_checker=gate,
                                   plan_builder=plans, context_factory=factory,
                                   skeleton_generator=lambda profile, payload: JavaConversionOutput(java_source=skeleton()),
                                   pass_factory=lambda profile, payload, context: make_pass_generator(profile, payload, context, model_call))


def implement(instruction, payload):
    request = json.loads(payload)
    from runtime.composer_behavior_context import COMPOSER_SECTIONS
    assert tuple(item["heading"] for item in request["composer_behavior_evidence"]) == COMPOSER_SECTIONS
    name = request["method_name"]
    body = ["return;"] if name in {"initializeContext", "enrichWithDbLookups"} else ["return null;"]
    return json.dumps(dict(java_source=replace_method_body(request["current_class"], name, body), dependencies=[]))


def test_skeleton_receives_required_composer_behavior(monkeypatch):
    from models.pipeline_configuration import PipelineConfiguration
    from runtime.operation_assembly.generation import generate_skeleton
    from runtime.composer_behavior_context import COMPOSER_SECTIONS
    def model(self, instruction, payload):
        request = json.loads(payload)
        assert tuple(item["heading"] for item in request["composer_behavior_evidence"]) == COMPOSER_SECTIONS
        assert "mandatory composer_behavior_evidence" in instruction
        return json.dumps(dict(java_source=skeleton(), dependencies=[]))
    monkeypatch.setattr("runtime.operation_assembly.generation.AdkExecutor.execute", model)
    assert generate_skeleton(PipelineConfiguration(), {}).java_source == skeleton()


def test_assembly_completes_six_passes_and_reuses_checkpoint(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    calls = []
    model = lambda instruction, payload: calls.append(json.loads(payload)["method_name"]) or implement(instruction, payload)
    assert run(tmp_path, setup, plans, factory, gate, model) == "operation_review_pending"
    assert len(calls) == 6
    assert run(tmp_path, setup, plans, factory, gate, model) == "operation_review_pending"
    assert len(calls) == 6
    report = json.loads(run_report_path(tmp_path, "assembly_results.json").read_text())
    assert report[0]["reused"] is True


def test_unimplemented_stubs_are_not_assembly_success(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    model = lambda instruction, payload: json.dumps(dict(java_source=json.loads(payload)["current_class"], dependencies=[]))
    assert run(tmp_path, setup, plans, factory, gate, model) == "assembly_blocked"


def test_unapproved_gate_prevents_model_execution(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    calls = []
    assert run(tmp_path, setup, plans, factory, lambda: "gate_2_pending",
               lambda instruction, payload: calls.append(True)) == "component_gate_not_accepted"
    assert calls == []


def test_changes_outside_requested_method_are_rejected(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    def model(instruction, payload):
        output = json.loads(implement(instruction, payload))
        output["java_source"] += "\n// unrelated edit"
        return json.dumps(output)
    assert run(tmp_path, setup, plans, factory, gate, model) == "assembly_blocked"


def test_modified_assembled_source_is_not_reused(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    assert run(tmp_path, setup, plans, factory, gate, implement) == "operation_review_pending"
    report = json.loads(run_report_path(tmp_path, "assembly_results.json").read_text())
    from pathlib import Path
    path = Path(report[0]["service_path"])
    path.write_text(path.read_text() + "\n// changed")
    calls = []
    model = lambda instruction, payload: calls.append(True) or implement(instruction, payload)
    assert run(tmp_path, setup, plans, factory, gate, model) == "operation_review_pending"
    assert len(calls) == 6


def test_failed_assembly_retry_budget_survives_resume(tmp_path):
    setup, plans, factory, gate = assembly_setup(tmp_path)
    calls = []
    def invalid(instruction, payload):
        calls.append(True)
        output = json.loads(implement(instruction, payload))
        output["java_source"] += "\n// unrelated change"
        return json.dumps(output)
    for _ in range(setup[1].max_agent_task_retries + 1):
        assert run(tmp_path, setup, plans, factory, gate, invalid) == "assembly_blocked"
    assert len(calls) == setup[1].max_agent_task_retries
