"""Require the configured JDK in all native prompts without invalidating accepted units."""

import json
import pytest
from agents.behavior_conversion.configured_step import INSTRUCTION as STEP
from agents.behavior_conversion.format_mapping import INSTRUCTION as FORMAT
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from tests.runtime.test_behavior_conversion import state, profile, bundle
from tools.state_store_tools.behavior_units import snapshot


@pytest.mark.parametrize("java_version", [21, 25])
@pytest.mark.parametrize("kind,instruction", [("request_unformat", FORMAT),
    ("response_format", FORMAT), ("configured_step", STEP)], ids=["request", "response", "step"])
def test_configured_target_reaches_first_native_request(java_version, kind, instruction):
    conn, config = state()
    seen = []
    def model(text, encoded):
        seen.append(text)
        assert f"Configured Java target: Java {java_version}" in text
        assert f"test code, and proposed dependencies must support Java {java_version}" in text
        assert f"Tests must compile and execute on Java {java_version}" in text
        assert "Preserve existing dependency versions and scopes" in text
        assert "report the conflict in unresolved_questions" in text
        assert "incomplete replacements" in text
        return bundle().model_dump_json()
    generate(conn, config, profile(java_version=java_version), "unit", kind, instruction,
             {"kind": kind, "java_version": java_version}, NativeUnitBundle, model_call=model)
    assert len(seen) == 1


@pytest.mark.parametrize("kind,instruction", [("request_unformat", FORMAT), ("configured_step", STEP)])
def test_new_java_guidance_reuses_accepted_outputs_without_changing_compatibility(monkeypatch, kind, instruction):
    conn, config = state()
    settings = profile(java_version=25)
    payload = {"kind": kind, "java_version": 25}
    import agents.behavior_conversion.native_instructions as shared
    actual = shared.java_compatibility_instruction
    monkeypatch.setattr(shared, "java_compatibility_instruction", lambda version: "")
    output, fingerprint = generate(conn, config, settings, "unit", kind, instruction, payload,
                                  NativeUnitBundle, model_call=lambda *args: bundle().model_dump_json())
    previous = snapshot(conn, config.run_id, "compatibility:unit", kind)
    monkeypatch.setattr(shared, "java_compatibility_instruction", actual)
    validated = []
    cached, original = generate(conn, config, settings, "unit", kind, instruction, payload,
        NativeUnitBundle, validator=lambda output, cached: validated.append(cached),
        model_call=lambda *args: pytest.fail("Prompt wording invalidated accepted unit"))
    assert cached == output and original == fingerprint
    assert validated == [True]
    assert snapshot(conn, config.run_id, "compatibility:unit", kind)["fingerprint"] == previous["fingerprint"]
    assert conn.execute("SELECT count(*) FROM behavior_attempts").fetchone()[0] == 1
