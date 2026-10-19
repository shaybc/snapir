"""Keep implementation, route planning and scenario requests phase-specific."""

import json

from models.native_unit_bundle import NativeUnitBundle
from tests.runtime.test_incremental_operation import setup, invoke, Model, implementation


class Capture(Model):
    """Capture exact initial/correction instructions without live provider calls."""

    def __init__(self, reject_implementation=False, fail_scenario=False):
        super().__init__()
        self.calls = []
        self.reject_implementation = reject_implementation
        self.fail_scenario = fail_scenario

    def __call__(self, instruction, encoded):
        request = json.loads(encoded)
        self.calls.append((instruction, request))
        if request["assembly_phase"] == "implementation_compile" and self.reject_implementation:
            self.reject_implementation = False
            candidate = implementation()
            candidate.files.append(candidate.files[0].model_copy(update={"path": "src/test/java/StrayTest.java"}))
            return candidate.model_dump_json()
        if request["assembly_phase"] == "single_route_test" and self.fail_scenario:
            self.fail_scenario = False
            return NativeUnitBundle(files=[dict(path="src/main/java/Wrong.java", content="public class Wrong {}")]).model_dump_json()
        return super().__call__(instruction, encoded)


def test_implementation_initial_and_correction_have_no_test_generation_guidance(tmp_path):
    model = Capture(reject_implementation=True)
    values = setup(tmp_path)
    invoke(tmp_path, values, model)
    calls = [(instruction, request) for instruction, request in model.calls if request["assembly_phase"] == "implementation_compile"]
    assert len(calls) == 2
    assert "main implementation files only" in calls[1][1]["correction_feedback"]
    for instruction, request in calls:
        assert "main files only" in instruction
        assert "No test files" in instruction
        assert "testing_contract" not in request
        assert "Follow the versioned testing_contract" not in instruction
        assert "Tests must compile and execute" not in instruction
        assert "matching metadata and tests" not in instruction
        assert "its callers, metadata and tests" not in instruction
        assert "full test suite will rerun" not in instruction
        assert "Copy every accepted_units" in instruction
        assert "omit DTO/wire APIs" in instruction
        assert "dependency_units" in instruction and "evidence_ids" in instruction
        assert "support Java 25" in instruction
    assert values[3].get("testing_contract"), "Phase preparation must not mutate the original payload"


def test_plan_is_description_only_and_scenario_corrections_keep_test_template(tmp_path):
    model = Capture(fail_scenario=True)
    invoke(tmp_path, setup(tmp_path), model)
    plan = [(instruction, request) for instruction, request in model.calls if request["assembly_phase"] == "route_test_plan"]
    assert len(plan) == 1
    instruction, request = plan[0]
    assert "not code" in instruction and "No Java" in instruction
    assert "assertion focus is not its execution boundary" in instruction
    assert "another source key in routing_graph is an intermediate step, not terminal" in instruction
    assert "every downstream step" in instruction
    assert "every target must equal the next" in instruction
    assert "expected final result" in instruction
    assert "testing_contract" not in request
    assert request["assembled_code"] and request["closure"]["routing_graph"]
    assert "failed_sources" not in instruction
    scenarios = [(instruction, request) for instruction, request in model.calls if request["assembly_phase"] == "single_route_test"]
    assert len(scenarios) == 3
    assert any(request.get("correction_feedback") for _, request in scenarios)
    for instruction, request in scenarios:
        assert "exactly one focused operation test" in instruction
        assert "testing_contract" in request and request["testing_contract"]["examples"]
        assert "correct only the assigned scenario" in instruction
        assert "Do not weaken assertions" in instruction
        assert "corrected bundle, including matching metadata and tests" not in instruction
        assert "No main files" in instruction
        assert request["expected_test_path"].startswith("src/test/java/")


def test_accepted_phases_are_reused_after_prompt_separation(tmp_path):
    values = setup(tmp_path)
    model = Capture()
    _, first = invoke(tmp_path, values, model)
    before = len(model.calls)
    _, second = invoke(tmp_path, values, model)
    assert first == second and len(model.calls) == before
