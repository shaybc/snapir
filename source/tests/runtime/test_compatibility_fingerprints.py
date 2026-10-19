"""Preserve accepted behavior across prompt edits and invalidate versioned obligations."""

import json
from pathlib import Path
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.compatibility import compatibility_fingerprint, versioned_requirements
from tools.state_store_tools.behavior_units import save, snapshot
from tests.runtime.test_behavior_conversion import state, profile, bundle


def payload(kind="configured_step"):
    return {"kind": kind, "configuration_xml": '<step value="1"/>',
            "requirements": {"calculation": "Preserve calculation"}, "java_version": 25}


def model_with_coverage(requests):
    def model(instruction, encoded):
        request = json.loads(encoded)
        requests.append(request)
        output = bundle()
        test = output.files[1].path
        output.coverage = {name: [test] for name in request["requirements"]}
        return output.model_dump_json()
    return model


def test_prompt_model_and_example_changes_reuse_accepted_unit_with_two_saved_fingerprints():
    conn, config = state()
    calls = []
    first, original = generate(conn, config, profile(), "unit", "step", "Original wording", payload(),
        NativeUnitBundle, model_call=model_with_coverage(calls))
    current, fingerprint = generate(conn, config, profile(model_name="another-model"), "unit", "step",
        "Clearer wording and a better correction example", payload(), NativeUnitBundle,
        model_call=lambda *args: pytest.fail("Accepted unit regenerated"))
    assert current == first and fingerprint == original
    assert len(calls) == 1
    compat = snapshot(conn, config.run_id, "compatibility:unit", "step")
    assert compat["fingerprint"] != original
    assert json.loads(compat["data_json"])["requirement_versions"] == {"calculation": 1}
    assert json.loads(compat["data_json"])["request_fingerprint"] == original


def test_requirement_version_changes_only_affected_kinds_and_supplies_contract_to_model():
    conn, config = state()
    calls = []
    for name, kind in [("format", "request_unformat"), ("step", "configured_step")]:
        generate(conn, config, profile(), "unit", name, "Convert", payload(kind), NativeUnitBundle,
                 model_call=model_with_coverage(calls))
    settings = profile(conversion_requirements=[dict(requirement_id="calculation", version=2,
        description="Preserve calculation with business event logging", applies_to=["configured_step"])])
    generate(conn, config, settings, "unit", "format", "Updated prompt", payload("request_unformat"),
             NativeUnitBundle, model_call=lambda *args: pytest.fail("Unaffected format invalidated"))
    generate(conn, config, settings, "unit", "step", "Updated prompt", payload(), NativeUnitBundle,
             model_call=model_with_coverage(calls))
    assert len(calls) == 3
    assert calls[-1]["versioned_requirements"] == [dict(requirement_id="calculation", version=2,
        description="Preserve calculation with business event logging")]
    assert json.loads(snapshot(conn, config.run_id, "compatibility:unit", "step")["data_json"])["requirement_versions"] == {"calculation": 2}


def test_new_requirement_requires_coverage_and_is_not_satisfied_by_old_acceptance():
    conn, config = state()
    calls = []
    generate(conn, config, profile(), "unit", "step", "Convert", payload(), NativeUnitBundle,
             model_call=model_with_coverage(calls))
    settings = profile(max_agent_task_retries=1, conversion_requirements=[dict(requirement_id="business-logging",
        version=1, description="Emit the required business event", applies_to=["configured_step"])])
    with pytest.raises(ValueError, match="business-logging"):
        generate(conn, config, settings, "unit", "step", "Convert", payload(), NativeUnitBundle,
                 model_call=lambda *args: bundle().model_dump_json())


@pytest.mark.parametrize("change", ["xml", "java", "dependency", "api"])
def test_behavior_changes_invalidate_acceptance(change):
    conn, config = state()
    original = payload()
    sample = bundle()
    original["known_dependencies"] = [dict(group_id="org.example", artifact_id="client", version="1.0", scope="compile")]
    from models.maven_dependency import MavenDependency
    sample.dependencies = [MavenDependency(group_id="org.example", artifact_id="client", version="1.0", reason="Client")]
    original["converted_dependency_apis"] = [dict(unit_id="helper", planned_apis=[dict(type_name="com.company.generated.Step", method_signatures=["public int run()"] )])]
    first = []
    generate(conn, config, profile(), "unit", "step", "Convert", original, NativeUnitBundle,
        model_call=lambda *args: sample.model_dump_json())
    current = json.loads(json.dumps(original))
    settings = profile()
    if change == "xml": current["configuration_xml"] = '<step value="2"/>'
    if change == "java": settings = profile(java_version=21)
    if change == "dependency": current["known_dependencies"][0]["version"] = "2.0"
    if change == "api": current["converted_dependency_apis"][0]["planned_apis"][0]["method_signatures"] = ["public long run()"]
    generate(conn, config, settings, "unit", "step", "Convert", current, NativeUnitBundle,
        model_call=lambda *args: first.append(True) or sample.model_dump_json())
    assert first == [True]


def test_existing_six_units_bootstrap_and_revalidate_without_model_requests():
    fixture = json.loads((Path(__file__).parent / "fixtures/accepted_six_units.json").read_text(encoding="utf-8"))
    assert len(fixture) == 6
    conn, config = state()
    checked = []
    for item in fixture:
        identity, request, output = item["identity"], item["request"], item["output"]
        fp = item["request_fingerprint"]
        save(conn, config.run_id, "unit", identity, fp, output)
        conn.execute("INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?,?)",
            (config.run_id, "unit", identity, fp, 1, json.dumps(request), json.dumps(output), None, "fixture"))
        conn.commit()
        current = {key: value for key, value in request.items() if key not in
                   ("previous_model_response", "correction_feedback", "schema", "composer_behavior_evidence")}
        current.setdefault("known_dependencies", []).append(dict(group_id="org.example", artifact_id="unrelated", version="7.0", scope="compile"))
        def validate(candidate, cached):
            assert cached
            validate_bundle(candidate, candidate.unit_contract.apis, candidate.unit_contract.requirements,
                            candidate.evidence_ids)
            checked.append(identity)
        generate(conn, config, profile(), "unit", identity, "New wording and correction guidance", current,
            NativeUnitBundle, validator=validate, model_call=lambda *args: pytest.fail("Accepted legacy unit regenerated"))
        assert snapshot(conn, config.run_id, "compatibility:unit", identity)
    assert len(checked) == 6
    assert conn.execute("SELECT count(*) FROM behavior_attempts").fetchone()[0] == 6


def test_requirement_description_clarification_does_not_invalidate_same_version():
    conn, config = state()
    calls = []
    original = profile(conversion_requirements=[dict(requirement_id="calculation", version=1,
        description="Preserve calculation", applies_to=["configured_step"])])
    generate(conn, config, original, "unit", "step", "Convert", payload(), NativeUnitBundle,
             model_call=model_with_coverage(calls))
    clarified = profile(conversion_requirements=[dict(requirement_id="calculation", version=1,
        description="Clearer explanation of the same calculation", applies_to=["configured_step"])])
    generate(conn, config, clarified, "unit", "step", "Clearer prompt", payload(), NativeUnitBundle,
             model_call=lambda *args: pytest.fail("Unchanged requirement version regenerated"))
    assert len(calls) == 1


def test_unverifiable_legacy_acceptance_is_not_reused():
    conn, config = state()
    save(conn, config.run_id, "unit", "step", "unknown-legacy", bundle().model_dump(mode="json"))
    calls = []
    generate(conn, config, profile(), "unit", "step", "Convert", payload(), NativeUnitBundle,
             model_call=model_with_coverage(calls))
    assert len(calls) == 1


def test_legacy_units_are_invalidated_when_a_baseline_requirement_version_changes():
    item = json.loads((Path(__file__).parent / "fixtures/accepted_six_units.json").read_text(encoding="utf-8"))[0]
    conn, config = state()
    save(conn, config.run_id, "unit", item["identity"], item["request_fingerprint"], item["output"])
    conn.execute("INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?,?)", (config.run_id, "unit", item["identity"],
        item["request_fingerprint"], 1, json.dumps(item["request"]), json.dumps(item["output"]), None, "fixture"))
    conn.commit()
    calls = []
    settings = profile(conversion_requirements=[dict(requirement_id="business", version=2,
        description="Updated behavior requirement", applies_to=["request_unformat"])])
    def model(instruction, encoded):
        calls.append(json.loads(encoded))
        return json.dumps(item["output"])
    generate(conn, config, settings, "unit", item["identity"], "Convert", item["request"],
             NativeUnitBundle, model_call=model)
    assert len(calls) == 1
    assert calls[0]["versioned_requirements"][0]["version"] == 2


def test_legacy_reuse_still_requires_current_validation():
    item = json.loads((Path(__file__).parent / "fixtures/accepted_six_units.json").read_text(encoding="utf-8"))[0]
    conn, config = state()
    save(conn, config.run_id, "unit", item["identity"], item["request_fingerprint"], item["output"])
    conn.execute("INSERT INTO behavior_attempts VALUES (?,?,?,?,?,?,?,?,?)", (config.run_id, "unit", item["identity"],
        item["request_fingerprint"], 1, json.dumps(item["request"]), json.dumps(item["output"]), None, "fixture"))
    conn.commit()
    def reject(output, cached):
        assert cached
        raise ValueError("Accepted source manifest changed")
    with pytest.raises(ValueError, match="manifest changed"):
        generate(conn, config, profile(), "unit", item["identity"], "Updated wording", item["request"],
                 NativeUnitBundle, validator=reject, model_call=lambda *args: pytest.fail("Unsafe regeneration"))
    assert snapshot(conn, config.run_id, "compatibility:unit", item["identity"]) is None


def test_review_corrections_regenerate_but_corrected_acceptance_survives_wording_changes():
    conn, config = state()
    calls = []
    generate(conn, config, profile(), "unit", "step", "Convert", payload(), NativeUnitBundle,
             model_call=model_with_coverage(calls))
    correction = dict(payload(), behavior_review_feedback={"issues": ["Preserve the evidenced calculation"]},
                      previous_bundle=bundle().model_dump(mode="json"))
    generate(conn, config, profile(), "unit", "step", "Convert", correction, NativeUnitBundle,
             model_call=model_with_coverage(calls))
    assert len(calls) == 2
    generate(conn, config, profile(), "unit", "step", "Better wording", payload(), NativeUnitBundle,
             model_call=lambda *args: pytest.fail("Corrected accepted unit regenerated"))
