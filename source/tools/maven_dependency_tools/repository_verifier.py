"""Verify proposed artifacts using the user's Maven repository configuration."""

import subprocess
import logging

from tools.maven_dependency_tools.command import maven_executable
import tempfile
from pathlib import Path
from zipfile import ZipFile
import json

from models.maven_dependency import MavenDependency
from tools.maven_dependency_tools.policy import validate_dependency_policy

logger = logging.getLogger(__name__)


class MavenRepositoryVerifier:
    """Resolve exact artifacts with Maven and inspect required APIs."""

    def __init__(self, settings_path: str, approved_repository_urls: list[str],
                 local_repository: str, timeout_seconds: int = 180):
        self.settings_path = str(Path(settings_path).resolve()) if settings_path else None
        self.local_repository = Path(local_repository).resolve() if local_repository else None
        self.timeout_seconds = timeout_seconds
        self.environment = None

    def _arguments(self):
        """Use Maven defaults unless an explicit settings or cache override is supplied."""
        arguments = [maven_executable(), "--batch-mode"]
        if self.settings_path:
            arguments.extend(["--settings", self.settings_path])
        if self.local_repository:
            arguments.append(f"-Dmaven.repo.local={self.local_repository}")
        return arguments

    def _run(self, arguments, directory):
        """Retain Maven commands and complete captured output in redacted run diagnostics."""
        from runtime.model_execution.error_details import sanitize_diagnostic
        logger.debug("Maven command: %s; directory: %s", sanitize_diagnostic(str(arguments)), directory)
        try:
            from runtime.java_toolchain import java_environment
            environment = self.environment or java_environment()
            if environment is not None:
                logger.debug("Maven JAVA_HOME: %s", environment["JAVA_HOME"])
            options = {"env": environment} if environment is not None else {}
            result = subprocess.run(arguments, cwd=directory, capture_output=True, text=True,
                                    check=False, timeout=self.timeout_seconds, **options)
        except Exception:
            logger.exception("Maven command could not complete")
            raise
        logger.debug("Maven exit code: %s\nstdout:\n%s\nstderr:\n%s", result.returncode,
                     sanitize_diagnostic(result.stdout or ""), sanitize_diagnostic(result.stderr or ""))
        return result

    def __call__(self, dependency) -> None:
        """Fetch a pinned target artifact and confirm requested classes exist in its JAR."""
        with tempfile.TemporaryDirectory(prefix="snapir-maven-verification-") as directory:
            result = self._run(self._arguments() + [
                "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get",
                f"-Dartifact={dependency.coordinates}", "-Dtransitive=false",
            ], directory)
            if result.returncode:
                raise ValueError(f"Maven could not resolve {dependency.coordinates} (exit code {result.returncode}). "
                                 "See logs/model_execution.log for the command and complete Maven output.")
            repository = self.local_repository
            if repository is None:
                location = self._run(self._arguments() + ["--quiet", "help:evaluate",
                    "-Dexpression=settings.localRepository", "-DforceStdout"], directory)
                if location.returncode or not location.stdout.strip():
                    raise ValueError("Maven could not report its effective local repository")
                import re
                repository = Path(re.sub(r"\x1b\[[0-9;]*m", "", location.stdout).strip())
        artifact = repository.joinpath(*dependency.group_id.split("."), dependency.artifact_id,
                                                 dependency.version, f"{dependency.artifact_id}-{dependency.version}.jar")
        with ZipFile(artifact) as jar:
            names = set(jar.namelist())
            for class_name in dependency.required_classes:
                if class_name.replace(".", "/") + ".class" not in names:
                    raise ValueError(f"Required API missing from {dependency.coordinates}: {class_name}")

    def compile_project(self, project_root, allowed_ibm_artifacts=(), *, goal="compile"):
        """Inspect resolved transitives before compiling with the user's Maven configuration."""
        project_root = Path(project_root)
        if goal not in {"compile", "install", "test", "package"}:
            raise ValueError("Unsupported managed build goal")
        with tempfile.TemporaryDirectory(prefix="snapir-maven-build-") as directory:
            tree_path = Path(directory) / "dependencies.json"
            arguments = self._arguments()
            resolved = self._run(arguments + ["org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree",
                                      "-DoutputType=json", f"-DoutputFile={tree_path}"], project_root)
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
            return self._run(arguments + [goal], project_root)
