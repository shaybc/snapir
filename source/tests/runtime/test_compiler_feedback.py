"""Replay compiler failures without class-specific fixes or live model calls."""

import json
from pathlib import Path
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.compiler_feedback import compiler_correction, CompilerCorrectionError
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.resume_budget import with_resume_budget
from tests.runtime.test_behavior_conversion import state, profile


def failures():
    return json.loads((Path(__file__).parent / "fixtures/latest_compiler_failure_responses.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_latest_diagnostics_sources_and_relevant_verified_api(index):
    saved = failures()[index]
    data = compiler_correction(saved["error"], saved["response"]["files"], saved["dependency_apis"])
    assert data["original_compiler_output"] == saved["error"]
    assert data["failed_sources"] == [saved["response"]["files"][0]]
    assert len(data["relevant_dependency_apis"]) == 1
    api = data["relevant_dependency_apis"][0]
    assert "TechnicalErrorStep" in str(api)
    assert "getErrorCategory" not in str(api) and "getErrorNumber" not in str(api)
    if index == 1:
        assert len(data["diagnostics"]) == 1
        error = data["diagnostics"][0]
        assert error["actual_type"] == "int" and error["required_type"] == "java.lang.String"
        assert "delegate.execute" in error["source_line"]
    else:
        assert len(data["diagnostics"]) == 2
        assert {d["details"]["symbol"] for d in data["diagnostics"]} == {
            "method getErrorCategory()", "method getErrorNumber()"}
        assert all(d["category"] == "missing_symbol" and d["line"] > 0 for d in data["diagnostics"])


def test_corrections_and_resume_receive_latest_candidate_and_preserve_original_feedback():
    saved = failures()
    conn, config = state()
    calls = []
    index = [0]
    def model(instruction, request):
        data = json.loads(request)
        calls.append(data)
        assert "compiler_correction" in instruction
        if index[0] > 0:
            previous = saved[min(index[0] - 1, 2)]
            context = data["compiler_correction"]
            assert context["failed_sources"] == [previous["response"]["files"][0]]
            assert context["original_compiler_output"] == previous["error"]
            assert data["correction_feedback"] == previous["error"]
            assert context["relevant_dependency_apis"]
        return json.dumps(saved[min(index[0], 2)]["response"])
    def validator(bundle, cached):
        error = saved[min(index[0], 2)]["error"]
        index[0] += 1
        if index[0] <= 3:
            raise ValueError(error)
    @with_resume_budget
    def resume():
        return generate(conn, config, profile(), "unit", "step", "Convert", {
            "converted_dependency_apis": saved[0]["dependency_apis"]}, NativeUnitBundle,
            validator=validator, model_call=model)
    with pytest.raises(ValueError, match="Candidate validation failed"):
        resume()
    resume()
    assert len(calls) == 4
    rows = conn.execute("SELECT response,error,request_json FROM behavior_attempts ORDER BY attempt").fetchall()
    assert len(rows) == 4
    assert all(row["response"] and row["error"] for row in rows[:3])
    assert "failed_compiler_context" in json.loads(rows[2]["request_json"])


def test_generic_unknown_error_and_argument_details():
    source = {"path": "src/main/java/demo/Client.java", "content": "package demo; class Client { void run() {} }"}
    error = "[ERROR] C:/temp/src/main/java/demo/Client.java:[1,37] method run cannot be applied to given types;\n  required: int\n  found: java.lang.String\n  reason: argument mismatch\n"
    data = compiler_correction(error, [source], [{"planned_apis": [{"type_name": "demo.Other"}]}])
    assert data["diagnostics"][0]["category"] == "argument_mismatch"
    assert data["diagnostics"][0]["details"] == {"required": "int", "found": "java.lang.String", "reason": "argument mismatch"}
    assert not data["relevant_dependency_apis"]
    assert compiler_correction("Invalid JSON", [source]) is None


def test_generic_mock_stubbing_feedback_targets_the_original_call_inference():
    source = dict(path='src/test/java/demo/ClientTest.java', content='''package demo;
import static org.mockito.Mockito.*;
class ClientTest {
 void test() { when(client.send(any(), any())).thenReturn(response); }
}''')
    error = '''[ERROR] C:/temp/src/test/java/demo/ClientTest.java:[4,45] no suitable method found for thenReturn(java.net.http.HttpResponse<java.lang.String>)
    method org.mockito.stubbing.OngoingStubbing.thenReturn(java.net.http.HttpResponse<java.lang.Object>) is not applicable
      (argument mismatch; java.net.http.HttpResponse<java.lang.String> cannot be converted to java.net.http.HttpResponse<java.lang.Object>)'''
    data = compiler_correction(error,[source])
    diagnostic = data['diagnostics'][0]
    assert diagnostic['category'] == 'mock_generic_return_mismatch'
    assert 'explicit method type argument' in diagnostic['correction']
    assert 'Casting the thenReturn value alone' in diagnostic['correction']
    assert diagnostic['details']['overload_diagnostics']
    assert data['failed_sources'] == [source]
    assert data['original_compiler_output'] == error
    from runtime.behavior_conversion.compiler_feedback import with_dependency_apis
    stored = dict(data,diagnostics=[dict(diagnostic,category='compiler_error',correction='Old generic guidance')])
    resumed = with_dependency_apis(stored,[])
    assert resumed['diagnostics'][0]['category'] == 'mock_generic_return_mismatch'
    assert 'explicit method type argument' in resumed['diagnostics'][0]['correction']
    assert stored['diagnostics'][0]['category'] == 'compiler_error'


def test_candidate_sources_captured_before_temporary_folder_is_deleted(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from runtime.behavior_conversion.bundle_output import accept_bundle
    from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
    saved = failures()[0]
    def factory(settings, project, artifact):
        pom = project / "pom.xml"
        initialize_managed_pom(str(pom), "demo", artifact, java_version=25)
        return SimpleNamespace(pom_path=str(pom), verifier=lambda dependency: None, allowed_ibm_artifacts=())
    monkeypatch.setattr("runtime.behavior_conversion.validation.build_candidate", lambda *args: SimpleNamespace(issues=[saved["error"]]))
    files = {f["path"]: f["content"] for f in saved["response"]["files"]}
    with pytest.raises(CompilerCorrectionError) as caught:
        accept_bundle(tmp_path / "candidate", files, factory, profile(), [])
    assert caught.value.compiler_correction["failed_sources"] == [saved["response"]["files"][0]]
    assert not (tmp_path / "candidate").exists()


def test_operation_assembly_feedback_uses_accepted_unit_apis():
    from runtime.behavior_conversion.compiler_feedback import request_dependency_apis
    saved = failures()[0]
    dependency = next(api for api in saved["dependency_apis"] if "TechnicalErrorStep" in str(api))
    request = {"accepted_units": {"technical": {"unit_id": dependency["unit_id"],
        "apis": dependency["planned_apis"], "public_api": dependency["verified_api_surface"]}}}
    data = compiler_correction(saved["error"], saved["response"]["files"], request_dependency_apis(request))
    assert len(data["relevant_dependency_apis"]) == 1
    assert data["relevant_dependency_apis"][0]["verified_api_surface"] == dependency["verified_api_surface"]


def test_unrecognized_diagnostic_preserves_source_and_raw_message():
    source = dict(path="src/test/java/demo/ValueTest.java", content="package demo; class ValueTest {}")
    error = "[ERROR] C:/temp/src/test/java/demo/ValueTest.java:[1,15] unexpected custom diagnostic"
    data = compiler_correction(error, [source])
    assert data["diagnostics"][0]["category"] == "compiler_error"
    assert data["failed_sources"] == [source]
    assert data["original_compiler_output"] == error


def test_request_return_mismatch_targets_caller_and_retains_accepted_contract():
    """A mapper returning business input must not be treated as returning its wire DTO."""
    from copy import deepcopy
    from runtime.behavior_conversion.compiler_feedback import request_dependency_apis, with_dependency_apis
    from agents.behavior_conversion.operation_route_tests import IMPLEMENTATION
    accepted = {"request": {"contract": {"apis": [{"type_name": "demo.RequestMapper",
        "method_signatures": ["public demo.BusinessInput unformat(java.lang.String)",
                              "public demo.BusinessInput toBusinessInput(demo.WireInput)"]}]},
        "public_api": {"src/main/java/demo/RequestMapper.java": {"public_declarations": [
            "public BusinessInput unformat(String xml)", "public BusinessInput toBusinessInput(WireInput wire)"]}}}}
    original = deepcopy(accepted)
    source = dict(path="src/main/java/demo/Service.java", content="""package demo;
class Service {
 void execute(String xml) {
  RequestMapper mapper = new RequestMapper();
  WireInput wire = mapper.unformat(xml);
  BusinessInput input = mapper.toBusinessInput(wire);
 }
}""")
    error = "[ERROR] C:/temp/src/main/java/demo/Service.java:[5,34] incompatible types: demo.BusinessInput cannot be converted to demo.WireInput"
    apis = request_dependency_apis({"accepted_units": accepted})
    feedback = compiler_correction(error, [source], apis)
    diagnostic = feedback["diagnostics"][0]
    assert diagnostic["accepted_call_candidates"] == [{"type_name": "demo.RequestMapper",
        "method_signatures": ["public demo.BusinessInput unformat(java.lang.String)"]}]
    assert "candidate caller, not an accepted callee contract" in diagnostic["correction"]
    assert "use it directly" in diagnostic["correction"]
    assert feedback["failed_sources"] == [source]
    stored = deepcopy(feedback)
    stored["diagnostics"][0].pop("accepted_call_candidates")
    stored["diagnostics"][0]["correction"] = "Match the required type"
    assert with_dependency_apis(stored, apis)["diagnostics"][0] == diagnostic
    assert accepted == original
    assert "unformat may already return" in IMPLEMENTATION
