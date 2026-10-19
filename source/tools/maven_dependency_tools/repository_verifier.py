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
        """Confirm required classes exist in the selected JDK, declared JAR or transitives."""
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
        missing = [name for name in dependency.required_classes if name.replace(".", "/") + ".class" not in names]
        if missing:
            from tools.maven_dependency_tools.platform_classes import platform_class_owners
            platform = platform_class_owners(missing, self.environment)
            for name, locations in platform.items():
                logger.debug("Verified required API %s in selected JDK %s; no Maven class owner is needed", name, locations)
            missing = [name for name in missing if name not in platform]
        if missing:
            from tools.maven_dependency_tools.class_ownership import discover_class_owners, class_owner_feedback
            with tempfile.TemporaryDirectory(prefix="snapir-maven-class-ownership-") as directory:
                owners = discover_class_owners(dependency, missing, repository, directory, self._arguments(), self._run)
            unresolved = {name: candidates for name, candidates in owners.items() if len(candidates) != 1}
            if unresolved:
                raise ValueError(class_owner_feedback(dependency, unresolved))
            for name, candidates in owners.items():
                logger.debug("Verified required API %s for %s in resolved transitive artifact %s (%s)",
                             name, dependency.coordinates, candidates[0]["coordinates"], candidates[0]["jar"])

    def resolved_runtime_classpath(self, dependency):
        """Resolve a proposed runtime dependency and its transitives for a JDK load probe."""
        from xml.etree import ElementTree
        import os
        with tempfile.TemporaryDirectory(prefix='snapir-driver-classpath-') as directory:
            root = ElementTree.Element('project', xmlns='http://maven.apache.org/POM/4.0.0')
            for key, value in (('modelVersion', '4.0.0'), ('groupId', 'snapir.verification'), ('artifactId', 'driver-probe'), ('version', '1')):
                ElementTree.SubElement(root, key).text = value
            node = ElementTree.SubElement(ElementTree.SubElement(root, 'dependencies'), 'dependency')
            for key, value in (('groupId', dependency.group_id), ('artifactId', dependency.artifact_id), ('version', dependency.version)):
                ElementTree.SubElement(node, key).text = value
            ElementTree.ElementTree(root).write(Path(directory) / 'pom.xml', encoding='utf-8', xml_declaration=True)
            output = Path(directory) / 'classpath.txt'
            result = self._run(self._arguments() + ['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath',
                '-DincludeScope=runtime', '-Dmdep.outputFile=' + str(output)], directory)
            if result.returncode or not output.is_file():
                raise ValueError('Cannot resolve runtime classpath for driver ' + dependency.coordinates)
            return output.read_text(encoding='utf-8').strip().split(os.pathsep)

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
