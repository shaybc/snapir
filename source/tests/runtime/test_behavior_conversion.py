"""Exercise option-two acceptance, durable correction, ownership and build evidence."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.behavior_unit import BehaviorUnitInput, SourceEvidence
from models.native_unit_bundle import NativeUnitBundle
from models.operation_data_contract import NativeApiContract, UnitContract
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.bundle_output import validate_bundle, accept_bundle, verify_manifest
from runtime.behavior_conversion.generation import EvidenceSummary, generate
from runtime.behavior_conversion.request_context import source_parts, encode_request
from runtime.behavior_conversion.scheduler import ordered_units
from runtime.behavior_conversion.validation import build_candidate
from tools.component_inventory_tools.behavior_unit_usage import plan_unit_ownership
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.runs import upsert_run
from tools.state_store_tools.behavior_units import snapshot


def state():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    upsert_run(conn, run_id="pilot", run_mode="single_channel")
    return conn, SimpleNamespace(run_id="pilot")


def profile(**kwargs):
    return PipelineConfiguration(conversion_strategy="behavior_units", model_provider="mock", **kwargs)


def unit(name="step", consumers=None, fingerprint="same"):
    return BehaviorUnitInput(unit_id=name, kind="configured_step", logical_id=name,
        configuration_xml='<opStep id="x"/>', consumers=consumers or ["WEB/Transfer"], fingerprint=fingerprint)


def bundle(value=1):
    return NativeUnitBundle(files=[
        dict(path="src/main/java/com/company/generated/Step.java", content=f"package com.company.generated; public class Step {{ public int run() {{ return {value}; }} }}"),
        dict(path="src/test/java/com/company/generated/StepTest.java", content="package com.company.generated; public class StepTest {}"),
    ], coverage={"calculation": ["src/test/java/com/company/generated/StepTest.java"]}, evidence_ids=["original"])


class Verifier:
    def __init__(self, failing=False, skipped=False):
        self.failing, self.skipped, self.calls = failing, skipped, []

    def __call__(self, dependency):
        pass

    def compile_project(self, project, allowed=(), *, goal="compile"):
        self.calls.append(goal)
        if self.failing:
            return subprocess.CompletedProcess([], 1, "Unknown method setValue", "")
        if goal == "test":
            reports = Path(project) / "target/surefire-reports"
            reports.mkdir(parents=True, exist_ok=True)
            sources = list((Path(project) / "src/test/java").rglob("*Test.java"))
            for path in sources or [Path(project) / "src/test/java/Step.java"]:
                name = path.relative_to(Path(project) / "src/test/java").as_posix().removesuffix(".java").replace("/", ".")
                (reports / ("TEST-" + name + ".xml")).write_text(f'<testsuite name="{name}" tests="1" skipped="{int(self.skipped)}" failures="0" errors="0"/>')
        return subprocess.CompletedProcess([], 0, "", "")


def factory(verifier):
    def context(settings, project, artifact):
        initialize_managed_pom(str(project / "pom.xml"), "com.company.generated", artifact, java_version=settings.java_version)
        return ManagedBuildContext(str(project / "pom.xml"), verifier)
    return context


def test_old_profiles_keep_legacy_strategy_and_new_strategy_is_explicit():
    assert PipelineConfiguration().conversion_strategy == "legacy_components"
    assert profile().conversion_strategy == "behavior_units"
    with pytest.raises(ValueError):
        PipelineConfiguration(conversion_strategy="invented")


def test_json_correction_is_saved_and_success_reused_without_model_call():
    conn, config = state()
    requests = []
    responses = iter(['{"findings":', '```json\n{"findings":["Reads amount"]}\n```'])
    def model(instruction, encoded):
        requests.append(json.loads(encoded))
        return next(responses)
    result, fingerprint = generate(conn, config, profile(), "analysis", "step", "Analyze", {"source": "{N}"}, EvidenceSummary, model_call=model)
    assert result.findings == ["Reads amount"]
    assert "correction_feedback" in requests[1]
    assert requests[0]["source"] == "{N}"
    cached, _ = generate(conn, config, profile(), "analysis", "step", "Analyze", {"source": "{N}"}, EvidenceSummary,
                         model_call=lambda *_: pytest.fail("Completed analysis was repeated"))
    assert cached == result
    assert snapshot(conn, "pilot", "analysis", "step")["error"] is None
    assert conn.execute("SELECT status,error_message FROM agent_tasks").fetchone()[:] == ("completed", None)
    assert fingerprint


def test_failed_correction_budget_survives_resume_and_new_evidence_resets_it():
    conn, config = state()
    calls = []
    def invalid(*_):
        calls.append(True)
        return "not JSON"
    for expected in ("Invalid JSON", "correction limit"):
        with pytest.raises(ValueError):
            generate(conn, config, profile(max_agent_task_retries=2), "analysis", "step", "Analyze", {}, EvidenceSummary, model_call=invalid)
    assert len(calls) == 2
    output, _ = generate(conn, config, profile(max_agent_task_retries=2), "analysis", "step", "Analyze", {"changed": True},
        EvidenceSummary, model_call=lambda *_: '{"findings":["New evidence"]}')
    assert output.findings == ["New evidence"]


def test_build_error_returns_targeted_feedback_before_acceptance(tmp_path):
    from runtime.behavior_conversion.runner import _bundle_validator
    conn, config = state()
    verifier = Verifier(failing=True)
    validate = _bundle_validator(conn, config, profile(), tmp_path / "project", "step", (), ("calculation",), ("original",), factory(verifier))
    requests = []
    def model(_, encoded):
        requests.append(json.loads(encoded))
        verifier.failing = len(requests) == 1
        return bundle().model_dump_json()
    output, _ = generate(conn, config, profile(), "unit", "step", "Convert", {}, NativeUnitBundle, validate, model)
    assert "Unknown method setValue" in requests[1]["correction_feedback"]
    assert output == bundle()
    assert (tmp_path / "project/src/main/java/com/company/generated/Step.java").exists()
    assert snapshot(conn, "pilot", "unit", "step")["status"] == "accepted"


def test_whole_units_use_distinct_consumers_and_contract_compatibility():
    settings = profile(shared_library_min_usage=2, broad_library_usage_threshold=3)
    units = [unit("first", ["WEB/A", "WEB/A"]), unit("second", ["WEB/B"])]
    ownership = plan_unit_ownership(units, settings)
    assert ownership.assignments["first"].startswith("shared-")
    assert ownership.assignments["first"] == ownership.assignments["second"]
    split = plan_unit_ownership(units, settings, {"first": "one-api", "second": "different-api"})
    assert set(split.assignments.values()) == {None}
    assert plan_unit_ownership([unit(consumers=["WEB/A", "WEB/B", "IVR/A", "IVR/B"])], settings).assignments["step"] == "common-lib"


def test_shared_units_are_first_only_when_their_dependencies_are_ready():
    units = [unit("local"), unit("shared"), unit("independent")]
    def contract(name, deps=()):
        return UnitContract(unit_id=name, apis=[NativeApiContract(type_name="com.company.generated." + name)], dependency_units=list(deps),
                            requirements={"r": "business rule"}, evidence_ids=["xml"])
    contracts = {"local": contract("local"), "shared": contract("shared", ["local"]), "independent": contract("independent")}
    ordered = ordered_units(units, contracts, {"local": None, "shared": "shared-lib", "independent": "shared-lib"})
    assert [item.unit_id for item in ordered] == ["independent", "local", "shared"]
    contracts["local"].dependency_units = ["shared"]
    with pytest.raises(ValueError):
        ordered_units(units, contracts, {item.unit_id: None for item in units})


@pytest.mark.parametrize("path", ["../Step.java", "src/main/java/../../Step.java", "C:/Step.java", "src/main/java/com/company/generated/Other.java"])
def test_bundle_rejects_unsafe_or_mismatched_paths(path):
    output = bundle()
    output.files[0].path = path
    with pytest.raises(ValueError):
        validate_bundle(output)


def test_bundle_rejects_framework_recreation_and_missing_api_or_test():
    output = bundle()
    validate_bundle(output, [NativeApiContract(type_name="com.company.generated.Step", method_signatures=["public int run()"])],
                    ["calculation"], ["original"])
    with pytest.raises(ValueError, match="contract"):
        validate_bundle(output, [NativeApiContract(type_name="com.company.generated.Step", method_signatures=["public int missing()"])] )
    with pytest.raises(ValueError, match="test"):
        validate_bundle(output, requirements=["uncovered"])
    output.files[0].path = "src/main/java/com/company/generated/Context.java"
    output.files[0].content = "package com.company.generated; public class Context {}"
    with pytest.raises(ValueError, match="recreate"):
        validate_bundle(output)


def test_build_failure_never_publishes_candidate(tmp_path):
    project = tmp_path / "candidate"
    with pytest.raises(ValueError, match="Unknown method"):
        accept_bundle(project, validate_bundle(bundle()), factory(Verifier(failing=True)), profile(), [])
    assert not project.exists()


def test_accepted_sources_cannot_be_changed_or_overwritten_by_another_bundle(tmp_path):
    files = validate_bundle(bundle())
    result, manifest = accept_bundle(tmp_path / "candidate", files, factory(Verifier()), profile(), [])
    assert result["tests_passed"] and result["test_count"] == 1
    assert result["behavioral_equivalence"] == "not_available"
    verify_manifest(tmp_path / "candidate", manifest)
    with pytest.raises(ValueError, match="overwrite"):
        accept_bundle(tmp_path / "candidate", validate_bundle(bundle(2)), factory(Verifier()), profile(), [])
    (tmp_path / "candidate" / next(iter(files))).write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        verify_manifest(tmp_path / "candidate", manifest)


def test_changed_owned_bundle_is_replaced_only_after_successful_build(tmp_path):
    project = tmp_path / "candidate"
    _, manifest = accept_bundle(project, validate_bundle(bundle()), factory(Verifier()), profile(), [])
    with pytest.raises(ValueError):
        accept_bundle(project, validate_bundle(bundle(2)), factory(Verifier(failing=True)), profile(), [], owned_files=manifest)
    verify_manifest(project, manifest)
    _, revised = accept_bundle(project, validate_bundle(bundle(2)), factory(Verifier()), profile(), [], owned_files=manifest)
    assert revised != manifest
    verify_manifest(project, revised)


def test_skipped_or_missing_tests_do_not_count_as_behavior_checks(tmp_path):
    verifier = Verifier(skipped=True)
    context = ManagedBuildContext(str(tmp_path / "pom.xml"), verifier)
    result = build_candidate(tmp_path, context)
    assert result.build_passed and not result.tests_passed and result.test_count == 0


def test_incremental_evidence_preserves_all_source_and_blocks_oversized_requests():
    source = SourceEvidence(identity="original", content="line one\nline two\nline three\n", content_hash="hash")
    parts = source_parts(source, 12)
    assert "".join(part["content"] for part in parts) == source.content
    assert [part["part"] for part in parts] == [1, 2, 3]
    request, encoded = encode_request({}, "Convert", 180000)
    assert "composer_behavior_evidence" in request
    with pytest.raises(ValueError, match="budget"):
        encode_request({"source": "x" * 200000}, "Convert", 180000)


def test_unrelated_operation_types_do_not_prevent_shared_unit_reuse():
    from runtime.behavior_conversion.contract_identity import unit_contract_identity
    contract = UnitContract(unit_id="step", apis=[NativeApiContract(type_name="com.company.generated.Step",
        method_signatures=["public Result run(Input input)"])], requirements={"r": "preserve"}, evidence_ids=["xml"])
    sources = [dict(path="Input.java", content="public class Input { Nested nested; }"),
               dict(path="Nested.java", content="public class Nested { int value; }"),
               dict(path="Result.java", content="public class Result { int value; }"),
               dict(path="Other.java", content="public class Other { int first; }")]
    first = unit_contract_identity(contract, sources)
    sources[-1]["content"] = "public class Other { String unrelated; }"
    assert unit_contract_identity(contract, sources) == first
    sources[1]["content"] = "public class Nested { String changed; }"
    assert unit_contract_identity(contract, sources) != first


def test_review_feedback_causes_bounded_correction_and_is_reused():
    from runtime.behavior_conversion.revisions import generate_reviewed_bundle
    conn, config = state()
    calls = []
    review_count = 0
    def model(_, encoded):
        nonlocal review_count
        request = json.loads(encoded)
        calls.append(request)
        if request["schema"]["title"] == "BehaviorReview":
            review_count += 1
            return json.dumps(dict(approved=review_count > 1, issues=["Wrong amount"] if review_count == 1 else []))
        return bundle(1 if "behavior_review_feedback" not in request else 2).model_dump_json()
    args = (conn, config, profile(), "unit", "step", "Convert", {}, lambda *args, **kwargs: None,
            lambda output: {"bundle": output.model_dump(mode="json")})
    output, _, review, _ = generate_reviewed_bundle(*args, model_call=model)
    assert review.approved and "return 2" in output.files[0].content
    assert len(calls) == 4 and calls[2]["behavior_review_feedback"]["issues"] == ["Wrong amount"]
    generate_reviewed_bundle(*args, model_call=lambda *_: pytest.fail("Accepted revision was repeated"))


def test_native_validation_corrections_target_only_owned_units_and_preserve_budget():
    from runtime.behavior_conversion.corrections import route_native_correction, correction_feedback
    conn, config = state()
    config.max_agent_task_retries = 1
    item = dict(channel="WEB", operation_id="Transfer", payload={"bindings": {"transfer": {"unit_id": "owned"}}})
    assert route_native_correction(conn, config, item, {"failure_class": "conversion_gap", "native_unit_ids": ["other"]}) == "human"
    result = dict(failure_class="conversion_gap", native_unit_ids=["owned"], findings=["Wrong amount"])
    assert route_native_correction(conn, config, item, result) == "component"
    assert correction_feedback(conn, "pilot", "unit", "owned")["validation_feedback"] == ["Wrong amount"]
    assert route_native_correction(conn, config, item, result) == "exhausted"
    assert route_native_correction(conn, config, item, {"failure_class": "routing_mismatch", "findings": ["Wrong next step"]}) == "assembly"
    assert correction_feedback(conn, "pilot", "service", "WEB/Transfer")["validation_feedback"] == ["Wrong next step"]
    assert route_native_correction(conn, config, item, {"failure_class": "build_failure"}) == "generation"


@pytest.mark.parametrize("kind", ["request_unformat", "response_format", "configured_step"])
def test_complete_bundle_keeps_xml_and_supporting_sources_without_analysis(kind):
    from runtime.behavior_conversion.generation import bounded_unit_evidence
    conn, config = state()
    target = unit().model_copy(update={"kind": kind})
    target.sources = [SourceEvidence(identity=name, content="public class " + name + " {}", content_hash=name)
                      for name in ("Formatter", "Decorator", "Helper")]
    evidence = bounded_unit_evidence(conn, config, profile(), target,
                                    model_call=lambda *_: pytest.fail("Normal bundle triggered analysis"))
    assert evidence == target.model_dump(mode="json")


def test_oversized_bundle_groups_sources_with_xml_and_retains_all_content():
    from runtime.behavior_conversion.generation import bounded_unit_evidence
    conn, config = state()
    target = unit()
    target.sources = [SourceEvidence(identity=str(index), content=("value = 1;\n" * 1600), content_hash=str(index))
                      for index in range(4)]
    requests = []
    def model(instruction, encoded):
        data = json.loads(encoded)
        requests.append(data)
        assert data["configuration_xml"] == target.configuration_xml
        assert data["unit_id"] == target.unit_id
        assert len(encoded) + len(instruction) <= 60000
        return json.dumps({"findings": ["Preserve behavior"]})
    result = bounded_unit_evidence(conn, config, profile(behavior_context_chars=60000), target, model)
    assert len(requests) > 1
    assert result["source_summaries"] and not result["sources"]
    for source in target.sources:
        actual = "".join(item["content"] for request in requests for item in request["sources"]
                         if item["identity"] == source.identity)
        assert actual == source.content



def test_oversized_bundle_packs_multiple_supporting_classes_in_each_part():
    from runtime.behavior_conversion.generation import bounded_unit_evidence
    conn, config = state()
    target = unit().model_copy(update={"kind": "request_unformat", "configuration_xml": '<CCXML name="Request"/>'})
    target.sources = [SourceEvidence(identity=str(index), content="x = 1;\n" * 100, content_hash=str(index))
                      for index in range(50)]
    requests = []
    def model(instruction, encoded):
        request = json.loads(encoded)
        requests.append(request)
        return json.dumps({"findings": ["Read configured request"]})
    bounded_unit_evidence(conn, config, profile(behavior_context_chars=60000), target, model)
    assert len(requests) > 1
    assert any(len(request["sources"]) > 1 for request in requests)
    assert [source for request in requests for source in request["sources"]] == [source.model_dump(mode="json") for source in target.sources]
    assert all(request["configuration_xml"] == target.configuration_xml for request in requests)



@pytest.mark.parametrize("source_type, body, offending", [
    ("Mapper", "import com.ibm.il.dse.cc.decorator.CCPadding; public class Mapper {}", "com.ibm.il.dse.cc.decorator.CCPadding"),
    ("FormatDecoratorHolder", "public class FormatDecoratorHolder {}", "FormatDecoratorHolder"),
    ("Context", "public class Context {}", "Context"),
])
def test_framework_correction_names_file_type_and_native_replacement(source_type, body, offending):
    conn, config = state()
    path = "src/main/java/com/company/generated/" + source_type + ".java"
    invalid = NativeUnitBundle(files=[dict(path=path, content="package com.company.generated;\n" + body)])
    requests = []
    def model(instruction, encoded):
        requests.append(json.loads(encoded))
        return (invalid if len(requests) == 1 else bundle()).model_dump_json()
    output, _ = generate(conn, config, profile(), "unit", source_type, "Generate native code", {},
        NativeUnitBundle, validator=lambda candidate, cached=False: validate_bundle(candidate), model_call=model)
    feedback = requests[1]["correction_feedback"]
    assert path in feedback
    assert offending in feedback
    assert "mapper" in feedback and "Jackson" in feedback
    assert "Remove" in feedback and "typed" in feedback
    assert requests[1]["previous_model_response"] == invalid.model_dump_json()
    assert output.files == bundle().files


def test_format_prompt_requires_plain_mapper_decorator_behavior():
    from agents.behavior_conversion.format_mapping import INSTRUCTION
    for phrase in ("plain mapper logic", "reverse order", "forward order", "FormatDecoratorHolder",
                   "CCPadding", "NilDecorator", "Do not recreate initializeFrom(Tag)", "typed result"):
        assert phrase in INSTRUCTION
