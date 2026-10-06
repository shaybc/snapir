"""Compile converted Java in its managed Maven project."""

import subprocess
from pathlib import Path

from models.maven_dependency import JavaConversionOutput
from tools.maven_dependency_tools.pom_manager import merge_dependencies, project_lock


def parse_conversion_output(output: str) -> JavaConversionOutput:
    """Require structured Java and dependency proposals in managed-project mode."""
    return JavaConversionOutput.model_validate_json(output)


def submit_managed_conversion(output: JavaConversionOutput, source_path: str, pom_path: str,
                              verifier, *, allowed_ibm_artifacts=(), allowed_ibm_classes=(), task_id="", settings_path=None):
    """Update the canonical POM and compile all available project sources together."""
    pom = Path(pom_path).resolve()
    source = Path(source_path).resolve()
    if not source.is_relative_to(pom.parent / "src/main/java"):
        raise ValueError("Managed Java output must be inside the project's src/main/java")
    from constants import FORBIDDEN_DEPENDENCIES
    from tools.validation_tools.ibm_dependency_guard_tool import scan_source
    findings = scan_source(output.java_source, FORBIDDEN_DEPENDENCIES, allowed_classes=allowed_ibm_classes)
    if findings:
        raise ValueError("Converted source retains prohibited dependencies: " + ", ".join(findings))
    merge_dependencies(str(pom), output.dependencies, verifier,
                       allowed_ibm_artifacts=allowed_ibm_artifacts, task_id=task_id)
    with project_lock(pom):
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(output.java_source, encoding="utf-8")
        command = ["mvn", "--batch-mode", "compile"]
        if settings_path:
            command.extend(["--settings", settings_path])
        if hasattr(verifier, "compile_project"):
            return verifier.compile_project(pom.parent, allowed_ibm_artifacts)
        return subprocess.run(command, cwd=pom.parent, capture_output=True, text=True, check=False, timeout=180)
