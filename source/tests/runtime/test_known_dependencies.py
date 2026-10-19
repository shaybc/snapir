"""Replay dependency conflicts and check first-request inventory for all known artifacts."""

import json
from pathlib import Path
import pytest
from agents.behavior_conversion.configured_step import INSTRUCTION as STEP
from agents.behavior_conversion.format_mapping import INSTRUCTION as FORMAT
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.dependency_context import known_dependencies
from runtime.behavior_conversion.generation import generate
from tools.maven_dependency_tools.pom_manager import merge_dependencies
from tests.runtime.test_behavior_conversion import state, profile


def saved_project(tmp_path):
    saved = json.loads((Path(__file__).parent / "fixtures/latest_dependency_version_responses.json").read_text(encoding="utf-8"))
    pom = tmp_path / "pom.xml"
    pom.write_text(saved["pom"], encoding="utf-8")
    return saved, pom


@pytest.mark.parametrize("attempt", [1, 2, 3])
def test_latest_responses_get_precise_conflicts_and_match_when_current_versions_are_used(tmp_path, attempt):
    saved, pom = saved_project(tmp_path)
    bundle = NativeUnitBundle.model_validate(saved["responses"][attempt - 1]["response"])
    original = pom.read_bytes()
    with pytest.raises(ValueError) as caught:
        merge_dependencies(str(pom), bundle.dependencies, lambda dependency: None)
    error = str(caught.value)
    assert "org.junit.jupiter:junit-jupiter" in error
    assert "Proposed version 5.10.2, scope test" in error
    assert "version=5.10.0 and scope=test" in error
    assert pom.read_bytes() == original
    current = {(d["group_id"], d["artifact_id"]): d for d in known_dependencies([tmp_path], [])}
    adjusted = [d.model_copy(update={"version": current[(d.group_id, d.artifact_id)]["version"],
                                   "scope": current[(d.group_id, d.artifact_id)]["scope"]}) for d in bundle.dependencies]
    # Isolate the second actual conflict after JUnit is corrected.
    mixed = [adjusted[0], bundle.dependencies[1]]
    with pytest.raises(ValueError, match="version=2.15.2 and scope=compile"):
        merge_dependencies(str(pom), mixed, lambda dependency: None)
    assert pom.read_bytes() == original
    merge_dependencies(str(pom), adjusted, lambda dependency: None)
    assert {(d["artifact_id"], d["version"], d["scope"]) for d in known_dependencies([tmp_path], [])} == {
        ("junit-jupiter", "5.10.0", "test"), ("jackson-dataformat-xml", "2.15.2", "compile"),
        ("jackson-databind", "2.15.2", "compile")}


@pytest.mark.parametrize("instruction", [STEP, FORMAT])
def test_first_request_and_correction_use_all_current_coordinates(tmp_path, instruction):
    saved, pom = saved_project(tmp_path)
    known = known_dependencies([tmp_path], [])
    conn, config = state()
    calls = []
    response = json.dumps(saved["responses"][0]["response"])
    def model(text, encoded):
        data = json.loads(encoded)
        calls.append(data)
        assert data["known_dependencies"] == known
        assert "5.10.0" in text and "2.15.2" in encoded
        assert "5.10.2" not in text and "2.17.2" not in text
        assert "EVERY known artifact" in text
        bundle = NativeUnitBundle.model_validate_json(response)
        if len(calls) > 1:
            assert "version=5.10.0 and scope=test" in data["correction_feedback"]
            assert data["previous_model_response"] == response
            by_key = {(d["group_id"], d["artifact_id"]): d for d in known}
            for dependency in bundle.dependencies:
                existing = by_key[(dependency.group_id, dependency.artifact_id)]
                dependency.version, dependency.scope = existing["version"], existing["scope"]
        return bundle.model_dump_json() if len(calls) > 1 else response
    def validate(bundle, cached):
        merge_dependencies(str(pom), bundle.dependencies, lambda dependency: None)
    result, _ = generate(conn, config, profile(), "unit", "latest", instruction,
                         {"known_dependencies": known}, NativeUnitBundle, validator=validate, model_call=model)
    assert len(calls) == 2
    assert result.dependencies[0].version == "5.10.0"
    assert result.dependencies[1].version == "2.15.2"


def test_generic_inventory_handles_properties_scopes_and_planned_dependencies(tmp_path):
    (tmp_path / "pom.xml").write_text('<project><properties><client.version>4.2</client.version></properties>'
        '<dependencies><dependency><groupId>org.example</groupId><artifactId>client</artifactId>'
        '<version>${client.version}</version><scope>provided</scope></dependency></dependencies></project>')
    planned = MavenDependency(group_id="org.example", artifact_id="native-helper", version="1.8", reason="Accepted helper")
    values = known_dependencies([tmp_path], [planned])
    assert [(d["artifact_id"], d["version"], d["scope"]) for d in values] == [
        ("client", "4.2", "provided"), ("native-helper", "1.8", "compile")]


def test_runner_supplies_pom_dependencies_to_units_and_service(tmp_path, monkeypatch):
    from tests.runtime.test_behavior_pipeline import setup, invoke, Model
    data = setup(tmp_path)
    conn, config, settings, closure, step = data
    project = Path(config.output_root) / "WEB/Transfer"
    project.mkdir(parents=True)
    saved_project(project)
    monkeypatch.setattr("runtime.service_generation.run_service_generation", lambda *args, **kwargs: "service_generation_blocked")
    model = Model()
    invoke(tmp_path, data, model)
    requests = [request for request in model.requests if request["schema"]["title"] == "NativeUnitBundle"]
    assert len(requests) == 2
    for request in requests:
        from runtime.behavior_conversion.testing_contract import TEST_PINS
        assert {(d["artifact_id"], d["version"], d["scope"]) for d in request["known_dependencies"]} == {
            ("junit-jupiter", "5.10.0", "test"), ("jackson-dataformat-xml", "2.15.2", "compile"),
            ("jackson-databind", "2.15.2", "compile"),
            *((artifact, version, "test") for _, artifact, version in TEST_PINS)}


def test_latest_response_builds_and_tests_offline_with_current_dependencies(monkeypatch, tmp_path):
    import shutil
    from types import SimpleNamespace
    from runtime.java_toolchain import java_scope
    from runtime.behavior_conversion.bundle_output import accept_bundle, validate_bundle
    from runtime.behavior_conversion.ownership import create_native_context
    from tools.maven_dependency_tools.build_context import ManagedBuildContext
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    cache = Path.home() / ".m2/repository"
    jdk = Path("C:/Program Files/Java/jdk-25.0.3")
    if not shutil.which("mvn") or not jdk.is_dir():
        pytest.skip("Offline Maven/JDK fixture unavailable")
    saved, pom = saved_project(tmp_path)
    bundle = NativeUnitBundle.model_validate(saved["responses"][-1]["response"])
    current = {(d["group_id"], d["artifact_id"]): d for d in known_dependencies([tmp_path], [])}
    for dependency in bundle.dependencies:
        existing = current[(dependency.group_id, dependency.artifact_id)]
        dependency.version, dependency.scope = existing["version"], existing["scope"]
    verifier = MavenRepositoryVerifier(None, [], str(cache))
    original = verifier._arguments
    monkeypatch.setattr(verifier, "_arguments", lambda: original() + ["--offline"])
    settings = profile(java_version=25, java_home=str(jdk))
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id="dependency-replay"), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / "pom.xml"), verifier))
    files = validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements, bundle.evidence_ids)
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path, files, context, settings, bundle.dependencies,
            required_tests={name for paths in bundle.coverage.values() for name in paths})
    assert result["build_passed"] and result["tests_passed"] and result["test_count"] > 0


def test_generic_scope_conflict_reports_exact_required_scope_without_changing_pom(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text('<project><dependencies><dependency><groupId>org.example</groupId>'
        '<artifactId>client</artifactId><version>4.2</version><scope>provided</scope>'
        '</dependency></dependencies></project>')
    original = pom.read_bytes()
    proposal = MavenDependency(group_id="org.example", artifact_id="client", version="4.2", scope="compile", reason="Client API")
    with pytest.raises(ValueError) as caught:
        merge_dependencies(str(pom), [proposal], lambda dependency: None)
    assert "Proposed version 4.2, scope compile" in str(caught.value)
    assert "version=4.2 and scope=provided" in str(caught.value)
    assert pom.read_bytes() == original


def test_dependency_management_and_properties_supply_known_values(tmp_path):
    (tmp_path / "pom.xml").write_text('<project><properties><version.number>8.1</version.number></properties>'
        '<dependencyManagement><dependencies><dependency><groupId>org.example</groupId>'
        '<artifactId>api</artifactId><version>${version.number}</version><scope>runtime</scope>'
        '</dependency></dependencies></dependencyManagement><dependencies><dependency>'
        '<groupId>org.example</groupId><artifactId>api</artifactId></dependency></dependencies></project>')
    values = known_dependencies([tmp_path], [])
    assert [(d["artifact_id"], d["version"], d["scope"]) for d in values] == [("api", "8.1", "runtime")]
