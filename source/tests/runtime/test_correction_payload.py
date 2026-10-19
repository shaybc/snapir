"""Replay the latest oversized assembly correction without losing its evidence."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from agents.behavior_conversion.operation_route_tests import IMPLEMENTATION, IMPLEMENTATION_COMPILER, implementation_dependencies
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.correction_payload import compact_correction
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.request_context import encode_request
from tests.runtime.test_behavior_conversion import state, profile


def latest_request():
    return json.loads((Path(__file__).parent / "fixtures/latest_assembly_correction_budget.json").read_text(encoding="utf-8"))


def test_latest_correction_fits_without_truncating_source_diagnostics_or_accepted_apis():
    payload = latest_request()
    original = deepcopy(payload)
    instruction = IMPLEMENTATION + IMPLEMENTATION_COMPILER + implementation_dependencies(25)
    assert len(json.dumps(payload, ensure_ascii=False)) + len(instruction) > 180000
    request, encoded = encode_request(payload, instruction, 180000)
    assert len(encoded) + len(instruction) <= 180000
    assert payload == original
    assert request["accepted_units"] == payload["accepted_units"]
    for field in ("diagnostics", "failed_sources", "relevant_dependency_apis"):
        assert request["compiler_correction"][field] == payload["compiler_correction"][field]
    previous = json.loads(payload["previous_model_response"])
    compact = json.loads(request["previous_model_response"])
    for file in compact["files"]:
        if file.get("content_ref"):
            assert file["content_ref"] == "compiler_correction.failed_sources[0].content"
            file["content"] = request["compiler_correction"]["failed_sources"][0]["content"]
            file.pop("content_ref")
    assert compact == previous
    assert request["compiler_correction"]["original_compiler_output_ref"] == "correction_feedback"
    assert request["correction_feedback"] == payload["compiler_correction"]["original_compiler_output"]
    assert len(request["compiler_correction"]["diagnostics"]) == 3


def test_latest_request_reaches_model_with_complete_response_saved():
    conn, config = state()
    payload = latest_request()
    response = payload["previous_model_response"]
    calls = []
    def model(instruction, encoded):
        request = json.loads(encoded)
        calls.append(request)
        assert request["compiler_correction"]["failed_sources"] == payload["compiler_correction"]["failed_sources"]
        assert request["accepted_units"] == payload["accepted_units"]
        assert "content_ref" in request["previous_model_response"]
        return response
    generate(conn, config, profile(java_version=25, behavior_context_chars=180000),
        "service_implementation", "INTERNET/TransferFundsOp", IMPLEMENTATION, payload,
        NativeUnitBundle, model_call=model, require_coverage=False)
    assert len(calls) == 1
    assert conn.execute("SELECT response FROM behavior_attempts").fetchone()[0] == response


def test_small_correction_and_initial_requests_are_not_compacted():
    payload = dict(compiler_correction={"failed_sources": [{"path": "A.java", "content": "source"}]},
                   previous_model_response=json.dumps({"files": [{"path": "A.java", "content": "source"}]}))
    request, _ = encode_request(payload, "Fix", 100000)
    assert request["previous_model_response"] == payload["previous_model_response"]
    assert "correction_content_references" not in request
    with pytest.raises(ValueError, match="context budget"):
        encode_request({"sources": [{"content": "x" * 100000}]}, "Convert", 20000)


def test_same_path_with_different_content_is_not_deduplicated():
    payload = dict(compiler_correction={"failed_sources": [{"path": "A.java", "content": "latest source"}]},
                   previous_model_response=json.dumps({"files": [{"path": "A.java", "content": "older source"}]}))
    compact = compact_correction(payload)
    assert compact == payload
    with pytest.raises(ValueError, match="context budget"):
        encode_request(latest_request(), IMPLEMENTATION, 100000)
