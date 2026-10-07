"""Verify proposed artifacts using Maven routed through approved mirrors."""

import subprocess

from tools.maven_dependency_tools.command import maven_executable
import tempfile
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
import json

from models.maven_dependency import MavenDependency
from tools.maven_dependency_tools.policy import validate_dependency_policy


class MavenRepositoryVerifier:
    """Resolve exact artifacts through an approved settings file and inspect required APIs."""

    def __init__(self, settings_path: str, approved_repository_urls: list[str],
                 local_repository: str, timeout_seconds: int = 180):
        self.settings_path = str(Path(settings_path).resolve())
        self.local_repository = Path(local_repository).resolve()
        self.timeout_seconds = timeout_seconds
        root = ElementTree.parse(self.settings_path).getroot()
        namespace = root.tag.partition("}")[0] + "}" if "}" in root.tag else ""
        mirrors = root.findall(f"{namespace}mirrors/{namespace}mirror")
        urls = {url.rstrip("/") for url in approved_repository_urls}
        if not mirrors or any(mirror.findtext(namespace + "url", "").rstrip("/") not in urls for mirror in mirrors):
            raise ValueError("Every Maven mirror must use an approved repository URL")
        if not any(mirror.findtext(namespace + "mirrorOf") == "*" for mirror in mirrors):
            raise ValueError("Approved Maven settings require a mirror for all repositories")

    def __call__(self, dependency) -> None:
        """Fetch a pinned target artifact and confirm requested classes exist in its JAR."""
        with tempfile.TemporaryDirectory(prefix="snapir-maven-verification-") as directory:
            empty_settings = Path(directory) / "global-settings.xml"
            empty_settings.write_text("<settings/>", encoding="utf-8")
            result = subprocess.run([
                maven_executable(), "--batch-mode", "--settings", self.settings_path,
                "--global-settings", str(empty_settings),
                f"-Dmaven.repo.local={self.local_repository}",
                "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get",
                f"-Dartifact={dependency.coordinates}", "-Dtransitive=false",
            ], cwd=directory, capture_output=True, text=True, check=False, timeout=self.timeout_seconds)
        if result.returncode:
            raise ValueError(f"Artifact verification failed: {dependency.coordinates}")
        artifact = self.local_repository.joinpath(*dependency.group_id.split("."), dependency.artifact_id,
                                                 dependency.version, f"{dependency.artifact_id}-{dependency.version}.jar")
        with ZipFile(artifact) as jar:
            names = set(jar.namelist())
            for class_name in dependency.required_classes:
                if class_name.replace(".", "/") + ".class" not in names:
                    raise ValueError(f"Required API missing from {dependency.coordinates}: {class_name}")

    def compile_project(self, project_root, allowed_ibm_artifacts=(), *, goal="compile"):
        """Inspect resolved transitives before compiling through approved Maven settings."""
        project_root = Path(project_root)
        if goal not in {"compile", "install", "test", "package"}:
            raise ValueError("Unsupported managed build goal")
        with tempfile.TemporaryDirectory(prefix="snapir-maven-build-") as directory:
            global_settings = Path(directory) / "settings.xml"
            global_settings.write_text("<settings/>", encoding="utf-8")
            tree_path = Path(directory) / "dependencies.json"
            arguments = [maven_executable(), "--batch-mode", "--settings", self.settings_path,
                         "--global-settings", str(global_settings), f"-Dmaven.repo.local={self.local_repository}"]
            resolved = subprocess.run(arguments + ["org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree",
                                      "-DoutputType=json", f"-DoutputFile={tree_path}"], cwd=project_root,
                                      capture_output=True, text=True, check=False, timeout=self.timeout_seconds)
            if resolved.returncode:
                return resolved
            nodes = json.loads(tree_path.read_text(encoding="utf-8")).get("children", [])
            while nodes:
                node = nodes.pop()
                validate_dependency_policy(MavenDependency(
                    group_id=node["groupId"], artifact_id=node["artifactId"], version=node["version"],
                    scope=node.get("scope") or "compile", reason="Resolved Maven dependency",
                ), allowed_ibm_artifacts)
                nodes.extend(node.get("children", []))
            return subprocess.run(arguments + [goal], cwd=project_root, capture_output=True,
                                  text=True, check=False, timeout=self.timeout_seconds)
