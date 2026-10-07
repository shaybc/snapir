"""Verify canonical POM updates and cleaner integration without external repositories."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree

import pytest

from models.maven_dependency import MavenDependency
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom, merge_dependencies
from tools.maven_dependency_tools.policy import validate_dependency_policy
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier


def dependency(artifact="client", version="1.0.0", group="org.example"):
    return MavenDependency(group_id=group, artifact_id=artifact, version=version, reason="Required API")


def create_pom(tmp_path):
    path = tmp_path / "pom.xml"
    initialize_managed_pom(str(path), "org.example", "service")
    return path


def test_merge_is_idempotent_and_audited(tmp_path):
    pom = create_pom(tmp_path)
    first = merge_dependencies(str(pom), [dependency()], lambda proposal: None, task_id="task")
    second = merge_dependencies(str(pom), [dependency()], lambda proposal: None)
    assert first == second
    assert len(ElementTree.parse(pom).findall(".//{*}dependency")) == 1
    assert json.loads((tmp_path / "dependency_audit.jsonl").read_text().splitlines()[0])["pom_hash"] == first


def test_conflict_leaves_pom_unchanged(tmp_path):
    pom = create_pom(tmp_path)
    merge_dependencies(str(pom), [dependency()], lambda proposal: None)
    original = pom.read_bytes()
    with pytest.raises(ValueError, match="conflict"):
        merge_dependencies(str(pom), [dependency("other"), dependency(version="2.0.0")], lambda proposal: None)
    assert pom.read_bytes() == original


def test_verification_failure_does_not_change_pom(tmp_path):
    pom = create_pom(tmp_path)
    original = pom.read_bytes()
    def reject(proposal):
        raise ValueError("Not in approved repository")
    with pytest.raises(ValueError):
        merge_dependencies(str(pom), [dependency()], reject)
    assert pom.read_bytes() == original


def test_parallel_writers_do_not_lose_dependencies(tmp_path):
    pom = create_pom(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda number: merge_dependencies(str(pom), [dependency(f"client-{number}")],
                                                           lambda proposal: None), range(8)))
    assert len(ElementTree.parse(pom).findall(".//{*}dependency")) == 8


def test_ibm_client_exception_does_not_allow_composer_runtime():
    client = dependency(group="com.ibm.mq")
    with pytest.raises(ValueError):
        validate_dependency_policy(client)
    validate_dependency_policy(client, [client.coordinates])
    runtime = dependency(group="com.ibm.wsbcc")
    with pytest.raises(ValueError):
        validate_dependency_policy(runtime, [runtime.coordinates])


def test_repository_settings_must_cover_all_repositories(tmp_path):
    settings = tmp_path / "settings.xml"
    settings.write_text("<settings><mirrors><mirror><url>https://approved.example</url><mirrorOf>central</mirrorOf></mirror></mirrors></settings>")
    with pytest.raises(ValueError, match="all repositories"):
        MavenRepositoryVerifier(str(settings), ["https://approved.example"], str(tmp_path / "cache"))


def test_managed_cleaner_uses_canonical_pom(monkeypatch, tmp_path):
    from tests.test_ibm_java_cleaner_agent import memory_conn, add_task, RUN_ID, TASK_ID
    from agents.source_conversion.ibm_java_cleaner.agent import run_ibm_java_cleaner_task
    pom = create_pom(tmp_path)
    calls = []
    def compiler(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("tools.maven_dependency_tools.conversion_submission.subprocess.run", compiler)
    conn = memory_conn()
    add_task(conn)
    output = json.dumps(dict(java_source="public class StepA {}", dependencies=[dependency().model_dump()]))
    result = run_ibm_java_cleaner_task(conn, TASK_ID, str(tmp_path / "src/main/java/StepA.java"), RUN_ID,
                                      lambda packet: output, managed_pom_path=str(pom),
                                      dependency_verifier=lambda proposal: None)
    assert result == "compiled"
    assert "compile" in calls[0]
    assert "client" in pom.read_text()


def test_generation_preserves_existing_canonical_pom(tmp_path):
    from agents.java_service_generation.agent import write_generated_project
    project = tmp_path / "INTERNET" / "Op"
    project.mkdir(parents=True)
    pom = project / "pom.xml"
    pom.write_text("canonical")
    write_generated_project({"./pom.xml": "replacement", "Application.java": "class Application {}"},
                            str(tmp_path), "INTERNET", "Op", preserve_pom=True)
    assert pom.read_text() == "canonical"


def test_source_guard_allows_only_exact_client_class():
    from tools.validation_tools.ibm_dependency_guard_tool import scan_source
    allowed = ["com.ibm.mq.Client"]
    assert scan_source("import com.ibm.mq.Client;", ["com.ibm"], allowed_classes=allowed) == []
    assert scan_source("import com.ibm.mq.Other;", ["com.ibm"], allowed_classes=allowed)
    assert scan_source("import com.ibm.wsbcc.Runtime;", ["com.ibm"], allowed_classes=["com.ibm.wsbcc.Runtime"])


def test_transitive_ibm_runtime_blocks_compilation(monkeypatch, tmp_path):
    settings = tmp_path / "settings.xml"
    settings.write_text("<settings><mirrors><mirror><url>https://approved.example</url><mirrorOf>*</mirrorOf></mirror></mirrors></settings>")
    verifier = MavenRepositoryVerifier(str(settings), ["https://approved.example"], str(tmp_path / "cache"))
    calls = []
    def maven(command, **kwargs):
        calls.append(command)
        from pathlib import Path
        output = next(item.split("=", 1)[1] for item in command if item.startswith("-DoutputFile="))
        Path(output).write_text(json.dumps(dict(children=[dict(groupId="com.ibm.wsbcc", artifactId="runtime", version="1.0.0", scope="compile")])))
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("tools.maven_dependency_tools.repository_verifier.subprocess.run", maven)
    with pytest.raises(ValueError, match="prohibited"):
        verifier.compile_project(tmp_path)
    assert len(calls) == 1


def test_managed_pom_targets_java_25_with_pinned_compiler_and_jdk_enforcement(tmp_path):
    pom = create_pom(tmp_path)
    root = ElementTree.parse(pom)
    assert root.findtext(".//{*}maven.compiler.release") == "25"
    assert root.findtext(".//{*}requireJavaVersion/{*}version") == "[25,26)"
    assert root.findtext(".//{*}plugin/{*}artifactId") == "maven-compiler-plugin"
    from runtime.service_generation.project_output import configure_executable_build
    from types import SimpleNamespace
    from constants import SPRING_BOOT_VERSION
    configure_executable_build(SimpleNamespace(pom_path=str(pom)))
    root = ElementTree.parse(pom)
    assert len(root.findall("{*}build")) == 1
    plugins = root.findall(".//{*}plugin")
    assert any(node.findtext("{*}artifactId") == "maven-compiler-plugin" for node in plugins)
    assert any(node.findtext("{*}artifactId") == "spring-boot-maven-plugin" and node.findtext("{*}version") == SPRING_BOOT_VERSION for node in plugins)


def test_existing_old_managed_pom_is_rejected_without_overwriting(tmp_path):
    pom = create_pom(tmp_path)
    pom.write_text(pom.read_text().replace(">25<", ">17<"))
    original = pom.read_bytes()
    with pytest.raises(ValueError, match="release=25"):
        initialize_managed_pom(str(pom), "org.example", "service")
    assert pom.read_bytes() == original


def test_maven_launcher_uses_path_discovery(monkeypatch):
    from tools.maven_dependency_tools.command import maven_executable
    monkeypatch.setattr("tools.maven_dependency_tools.command.shutil.which", lambda name: "C:/Maven/bin/mvn.cmd")
    assert maven_executable() == "C:/Maven/bin/mvn.cmd"
    monkeypatch.setattr("tools.maven_dependency_tools.command.shutil.which", lambda name: None)
    assert maven_executable() == "mvn"
