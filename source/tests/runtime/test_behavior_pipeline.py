"""Check complete native-unit integration with explicit offline model/build fixtures."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.native_unit_bundle import NativeUnitBundle
from models.behavior_unit import SourceEvidence
from runtime.behavior_conversion.runner import _convert_and_review
from runtime.human_gates import record_decision
from runtime.workspace_paths import run_report_path
from tests.runtime.test_behavior_conversion import state, profile, unit, factory, Verifier
from tools.state_store_tools.behavior_units import snapshot


class Model:
    """Return typed contract/bundle fixtures while inspecting the real request flow."""

    def __init__(self, reject_review=False):
        self.requests, self.reject_review = [], reject_review

    def __call__(self, instruction, encoded):
        data = json.loads(encoded)
        self.requests.append(data)
        assert data["composer_behavior_evidence"]
        title = data["schema"]["title"]
        assert title != "OperationDataContract", "Operation-wide contract request was sent"
        if title == "BehaviorReview":
            return json.dumps(dict(approved=not self.reject_review, issues=[],
                                   unresolved_questions=["Missing calculation behavior"] if self.reject_review else []))
        if title == "RouteTestPlan":
            return json.dumps(dict(scenarios=[dict(scenario_id="success", description="Execute the original successful path",
                inputs=["input=1"], dependency_setup=[], expected_outcome="result=1", expected_side_effects=[],
                covers=list(data["requirements"]), routes=[dict(source="transfer", outcome="on0Do", target="end")])]))
        assert title == "NativeUnitBundle"
        if data.get("assembly_phase") == "single_route_test":
            arguments = ", ".join("new " + item["type_name"] + "()" for item in data["operation_contract"]["step_dependencies"])
            return NativeUnitBundle(files=[dict(path=data["expected_test_path"], content="package " + data["test_package"] +
                "; public class " + data["test_class"] + " { @org.junit.jupiter.api.Test public void executesOriginalRoute() { " +
                "org.junit.jupiter.api.Assertions.assertEquals(1, new com.company.generated.TransferService(" + arguments + ").execute(1)); } }")]).model_dump_json()
        if "unit_id" in data:
            name, signature, body = data["logical_id"], "public int run(int input)", "return input;"
            requirements = data["requirements"]
            evidence_ids = data["evidence_ids"]
        else:
            name, signature, body = "TransferService", "public int execute(int input)", "int result = input; "
            step_dependencies = [dict(binding_id=item["binding_id"], unit_id=item["unit_id"],
                type_name=item["allowed_types"][0], parameter_name="step" + str(index), field_name="step" + str(index))
                for index, item in enumerate(data["required_step_dependencies"])]
            body += " ".join("result = this." + item["field_name"] + ".run(result);" for item in step_dependencies) + " return result;"
            requirements, evidence_ids = data["requirements"], []
        test_path = "src/test/java/com/company/generated/" + name + "Test.java"
        extra = {}
        if "unit_id" in data:
            extra["unit_contract"] = dict(unit_id=data["unit_id"], apis=[dict(type_name="com.company.generated." + name,
                method_signatures=[signature])], requirements=requirements, evidence_ids=evidence_ids,
                dependency_units=[item["unit_id"] for item in data["converted_dependency_apis"]])
        else:
            package = "com.company.generated"
            extra["operation_contract"] = dict(sources=[dict(path="src/main/java/com/company/generated/TransferService.java",
                content="package com.company.generated; public class TransferService {}")],
                units=[item["contract"] for item in {value["unit_id"]: value for value in data["accepted_units"].values()}.values()],
                service_api=dict(type_name=package + ".TransferService", method_signatures=[signature]),
                request_type="int", success_type="int", error_type="int", step_dependencies=step_dependencies)
        prefix = ""
        if "unit_id" not in data:
            prefix = " ".join("private final " + item["type_name"] + " " + item["field_name"] + ";" for item in step_dependencies)
            prefix += " public TransferService(" + ", ".join(item["type_name"] + " " + item["parameter_name"] for item in step_dependencies) + ") { "
            prefix += " ".join("this." + item["field_name"] + " = " + item["parameter_name"] + ";" for item in step_dependencies) + " } "
        files = [dict(path="src/main/java/com/company/generated/" + name + ".java",
            content="package com.company.generated; public class " + name + " { " + prefix + signature + " { " + body + " } }"),
            dict(path=test_path, content="package com.company.generated; public class " + name + "Test {}")]
        if data.get("assembly_phase") == "implementation_compile":
            files = files[:1]
        return NativeUnitBundle(**extra, files=files,
            coverage={} if data.get("assembly_phase") == "implementation_compile" else {key: [test_path] for key in requirements},
            evidence_ids=evidence_ids).model_dump_json()


def setup(tmp_path, policy="automatic"):
    conn, config = state()
    config.output_root = str(tmp_path / "generated")
    config.source_root = str(tmp_path)
    from agents.migration_planning.agent import write_migration_plan
    from tests.test_migration_planning import plan, batch, packet
    task = packet("Transfer").model_copy(update={"run_id": "pilot", "channel": "WEB"})
    saved = plan([batch("pilot", [task], is_pilot=True)]).model_copy(update={"run_id": "pilot"})
    write_migration_plan(conn, saved)
    xml = tmp_path / "transfer.xml"
    xml.write_text('<operation><opStep id="transfer" on0Do="end"/></operation>')
    settings = profile(gate_policies={str(number): policy for number in range(1, 5)})
    step = unit("step")
    step.logical_id = "TransferStep"
    step.sources = [SourceEvidence(identity=name, content="package legacy; public class " + name + " {}",
                                  content_hash=name) for name in ("TransferStep", "TransferHelper")]
    closure = dict(operation_id="Transfer", channel="WEB", routing_graph={"transfer": {"on0Do": "end"}},
                   source_xml_path=str(xml), ref_formats={}, conversion_components=[], conversion_components_checked=True,
                   blocking_issues=[], status="READY")
    return conn, config, settings, closure, step


def invoke(tmp_path, setup, model):
    conn, config, settings, closure, step = setup
    return _convert_and_review(conn, config, settings, tmp_path, [closure], {"WEB/Transfer": [step]},
        {step.unit_id: step}, {"WEB/Transfer": {"transfer": step.unit_id}}, factory(Verifier()), model)


@pytest.mark.parametrize("kind", ["configured_step", "request_unformat", "response_format"])
def test_units_flow_and_packaging_handoff_reuse_without_model_calls(tmp_path, monkeypatch, kind):
    setup_data = setup(tmp_path)
    setup_data[4].kind = kind
    packaged = []
    monkeypatch.setattr("runtime.service_generation.run_service_generation", lambda *args, **kwargs: packaged.append(args) or "service_generation_blocked")
    model = Model()
    invoke(tmp_path, setup_data, model)
    conn, config, settings, closure, step = setup_data
    accepted = snapshot(conn, "pilot", "operation", "WEB/Transfer")
    assert accepted["status"] == "accepted"
    assert packaged and len(packaged) == 1
    assert [data["schema"]["title"] for data in model.requests] == ["NativeUnitBundle", "BehaviorReview", "NativeUnitBundle", "RouteTestPlan", "NativeUnitBundle", "BehaviorReview"]
    for evidence in (model.requests[0],):
        assert evidence["method_contract_validation"] == "resolved-java-types-v1"
        assert evidence["configuration_xml"] == step.configuration_xml
        assert evidence["sources"] == [source.model_dump(mode="json") for source in step.sources]
        assert "source_summaries" not in evidence
    calls = len(model.requests)
    invoke(tmp_path, setup_data, model)
    assert len(model.requests) == calls
    assert len(packaged) == 2
    from runtime.behavior_conversion.evidence import collect_native_operation_evidence
    plan = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel="WEB", operation_id="Transfer")])])
    evidence = collect_native_operation_evidence(conn, config, settings, plan)[0]
    assert not evidence["issues"]
    assert "public TransferService(" in evidence["java_source"]
    assert "new TransferStep()" not in evidence["java_source"]
    assert "Context" not in evidence["java_source"]
    contract = json.loads(accepted["data_json"])
    (Path(contract["project"]) / next(iter(contract["files"]))).write_text("changed")
    assert collect_native_operation_evidence(conn, config, settings, plan)[0]["issues"]


def test_gate_two_requires_human_approval_before_operation_generation(tmp_path, monkeypatch):
    setup_data = setup(tmp_path, "human")
    monkeypatch.setattr("runtime.service_generation.run_service_generation", lambda *_args, **_kwargs: pytest.fail("Packaging preceded approval"))
    model = Model()
    invoke(tmp_path, setup_data, model)
    conn = setup_data[0]
    assert conn.execute("SELECT current_phase FROM runs").fetchone()[0] == "gate_2_pending"
    assert snapshot(conn, "pilot", "operation", "WEB/Transfer") is None
    record_decision(conn, "pilot", 2, run_report_path(tmp_path, "gate_2_report.txt").read_text(), "approved")
    invoke(tmp_path, setup_data, model)
    assert conn.execute("SELECT current_phase FROM runs").fetchone()[0] == "gate_3_pending"
    assert snapshot(conn, "pilot", "operation", "WEB/Transfer") is not None


def test_unresolved_behavior_blocks_review_instead_of_inventing_code(tmp_path, monkeypatch):
    setup_data = setup(tmp_path)
    model = Model(reject_review=True)
    invoke(tmp_path, setup_data, model)
    assert setup_data[0].execute("SELECT current_phase FROM runs").fetchone()[0] == "gate_2_blocked"
    assert snapshot(setup_data[0], "pilot", "operation", "WEB/Transfer") is None


@pytest.mark.parametrize("threshold, shared", [(2, True), (3, False)])
def test_two_consumers_get_shared_library_or_separate_local_copies(tmp_path, monkeypatch, threshold, shared):
    conn, config, settings, closure, step = setup(tmp_path)
    settings.shared_library_min_usage = threshold
    step.consumers = ["WEB/Transfer", "WEB/OtherTransfer"]
    second = dict(closure, operation_id="OtherTransfer")
    monkeypatch.setattr("runtime.service_generation.run_service_generation", lambda *_args, **_kwargs: "service_generation_blocked")
    model = Model()
    _convert_and_review(conn, config, settings, tmp_path, [closure, second],
        {name: [step] for name in step.consumers}, {step.unit_id: step},
        {name: {"transfer": step.unit_id} for name in step.consumers}, factory(Verifier()), model)
    records = [json.loads(snapshot(conn, "pilot", "operation", name)["data_json"]) for name in step.consumers]
    paths = [record["bindings"]["transfer"]["project"] for record in records]
    if shared:
        assert paths[0] == paths[1] and "behavior-libraries" in paths[0]
    else:
        assert paths[0] != paths[1]
        assert all(path == record["project"] for path, record in zip(paths, records))
    assert sum(request["schema"]["title"] == "NativeUnitBundle" and "unit_id" in request for request in model.requests) == 1




def test_separate_units_reuse_accepted_interfaces_without_contract_request(tmp_path, monkeypatch):
    conn, config, settings, closure, step = setup(tmp_path)
    second = step.model_copy(deep=True)
    second.unit_id = "second"
    second.logical_id = "SecondStep"
    second.fingerprint = "different"
    monkeypatch.setattr("runtime.service_generation.run_service_generation", lambda *_args, **_kwargs: "service_generation_blocked")
    model = Model()
    _convert_and_review(conn, config, settings, tmp_path, [closure], {"WEB/Transfer": [step, second]},
        {step.unit_id: step, second.unit_id: second}, {"WEB/Transfer": {"transfer": step.unit_id, "second": second.unit_id}},
        factory(Verifier()), model)
    requests = [data for data in model.requests if "unit_id" in data]
    assert len(requests) == 2
    assert not requests[0]["converted_dependency_apis"]
    assert requests[1]["converted_dependency_apis"][0]["unit_id"] == requests[0]["unit_id"]
    assert requests[1]["converted_dependency_apis"][0]["verified_api_surface"]
    assert all("units" not in request and "source_summaries" not in request for request in requests)
    assert all(request["schema"]["title"] != "OperationDataContract" for request in model.requests)
    assert conn.execute("SELECT count(*) FROM behavior_attempts WHERE category IN ('contract', 'contract_evidence')").fetchone()[0] == 0
