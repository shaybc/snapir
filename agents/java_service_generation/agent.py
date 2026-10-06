from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Callable
from contextlib import nullcontext

from constants import (
    AGENT_MODEL,
    COMMON_LIB_ARTIFACT_ID,
    COMMON_LIB_GROUP_ID,
    FORBIDDEN_DEPENDENCIES,
    JAVA_PACKAGE_BASE,
    JAVA_VERSION,
    MAX_AGENT_TASK_RETRIES,
    OUTPUT_ROOT,
    SPRING_BOOT_VERSION,
)
from tools.state_store_tools._json import dumps, utc_now
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


JAVA_SERVICE_GENERATION_INSTRUCTION = """
You are generating a complete Java Spring Boot microservice for a single operation.

Generate a Spring Boot project that wraps the validated native Java service class.
Follow the package structure and separation-of-concerns rules from spring_boot_structure.md.

OPERATION_ID: {operation_id}
CHANNEL: {channel}
SERVICE_CLASS_SOURCE: {native_java_service}
JAXB_REQUEST_DTO: {request_dto_source}
JAXB_REPLY_DTO: {reply_dto_source}
JAXB_ERROR_DTO: {error_dto_source}
CONTEXT_CLASS: {context_class_source}
REPOSITORY_INTERFACES: {repository_sources}
JAVA_PACKAGE_BASE: {java_package_base}
SPRING_BOOT_VERSION: {spring_boot_version}
JAVA_VERSION: {java_version}

Output a JSON map: {"relative_file_path": "file_content", ...}
Include EVERY file. No explanation.
"""


ProjectGenerator = Callable[[str | None], str | dict[str, str]]


def parse_generated_project_output(output: str | dict[str, str]) -> dict[str, str]:
    """Parse an LLM project file map into relative paths and file contents."""
    if isinstance(output, dict):
        files = output
    else:
        text = output.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        files = json.loads(text)
    if not isinstance(files, dict) or not files:
        raise ValueError("Generated project output must be a non-empty JSON object")
    for relative_path, content in files.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("Generated project paths must be non-empty strings")
        if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            raise ValueError(f"Generated project path is not safe: {relative_path}")
        if not isinstance(content, str):
            raise ValueError(f"Generated project content must be text: {relative_path}")
    return files


def validate_generated_project(files: dict[str, str], operation_id: str, *, build_context=None) -> list[str]:
    """Return structural and dependency issues in a generated Spring Boot project."""
    issues = []
    required_suffixes = [
        "pom.xml",
        "src/main/resources/application.properties",
        "Application.java",
        f"controller/{operation_id}Controller.java",
        f"service/{operation_id}ServiceImpl.java",
        "xml/JaxbConfig.java",
        "error/GlobalExceptionHandler.java",
    ]
    normalized_paths = {_normalize_path(path): content for path, content in files.items()}
    for suffix in required_suffixes:
        if not any(path.endswith(_normalize_path(suffix)) for path in normalized_paths):
            issues.append(f"missing required file: {suffix}")
    controller_path = _find_suffix(normalized_paths, f"controller/{operation_id}Controller.java")
    if controller_path and _controller_has_business_logic(normalized_paths[controller_path]):
        issues.append("controller contains business logic")
    repository_paths = [path for path in normalized_paths if "/repository/" in path and path.endswith(".java")]
    for repository_path in repository_paths:
        if "JdbcTemplate" not in normalized_paths[repository_path]:
            issues.append(f"repository missing JdbcTemplate: {repository_path}")
    pom_path = _find_suffix(normalized_paths, "pom.xml")
    if pom_path:
        pom = normalized_paths[pom_path]
        for forbidden in FORBIDDEN_DEPENDENCIES:
            if build_context is not None and forbidden == "com.ibm":
                continue
            if forbidden.lower() in pom.lower():
                issues.append(f"pom contains forbidden dependency: {forbidden}")
        if COMMON_LIB_GROUP_ID not in pom or COMMON_LIB_ARTIFACT_ID not in pom:
            issues.append("pom missing common-lib dependency")
        if build_context is not None:
            from xml.etree import ElementTree
            from models.maven_dependency import MavenDependency
            from tools.maven_dependency_tools.policy import validate_dependency_policy
            try:
                root = ElementTree.fromstring(pom)
                for node in root.findall(".//{*}dependency"):
                    validate_dependency_policy(MavenDependency(
                        group_id=node.findtext("{*}groupId"), artifact_id=node.findtext("{*}artifactId"),
                        version=node.findtext("{*}version"), scope=node.findtext("{*}scope", "compile"),
                        reason="Managed service dependency"), build_context.allowed_ibm_artifacts)
            except ValueError as exc:
                issues.append(str(exc))
    return issues


def write_generated_project(
    files: dict[str, str],
    output_root: str,
    channel: str,
    operation_id: str,
    *,
    preserve_pom: bool = False,
) -> Path:
    """Write a generated Spring Boot project under the operation output directory."""
    project_root = Path(output_root) / channel / operation_id
    for relative_path, content in files.items():
        destination = project_root / relative_path
        if preserve_pom and destination.resolve() == (project_root / "pom.xml").resolve():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return project_root


def run_java_service_generation_agent(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    generator: ProjectGenerator,
    *,
    output_root: str = OUTPUT_ROOT,
    managed_pom_path: str | None = None,
    build_context=None,
) -> str:
    """Generate, compile, retry, and persist a Spring Boot microservice project."""
    task = get_agent_task(conn, task_id)
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES) if task else MAX_AGENT_TASK_RETRIES
    compiler_error = None
    validation_errors: list[str] = []
    if build_context is not None:
        managed_pom_path = build_context.pom_path
    for attempt in range(1, max_retries + 1):
        files = parse_generated_project_output(generator(compiler_error))
        if managed_pom_path:
            expected = (Path(output_root) / channel / operation_id / "pom.xml").resolve()
            if Path(managed_pom_path).resolve() != expected:
                raise ValueError("Managed POM must be the final service project's pom.xml")
            files["pom.xml"] = expected.read_text(encoding="utf-8")
        validation_errors = validate_generated_project(files, operation_id, build_context=build_context)
        if validation_errors:
            compiler_error = "\n".join(validation_errors)
            continue
        if managed_pom_path:
            from tools.maven_dependency_tools.pom_manager import project_lock
            build_lock = project_lock(Path(managed_pom_path).resolve())
        else:
            build_lock = nullcontext()
        with build_lock:
            project_root = write_generated_project(files, output_root, channel, operation_id,
                                                   preserve_pom=bool(managed_pom_path))
            compile_result = (build_context.verifier.compile_project(project_root, build_context.allowed_ibm_artifacts)
                              if build_context is not None else _mvn_compile(project_root))
        if compile_result.returncode == 0:
            upsert_generated_artifact(
                conn,
                artifact_id=f"{run_id}:java_service:{operation_id}:{task_id}",
                run_id=run_id,
                operation_id=operation_id,
                channel=channel,
                target_language="java",
                artifact_kind="service",
                generated_path=str(project_root),
                status="converted",
                blocking_reason=None,
                attempt_number=attempt,
            )
            if task:
                update_task_status(conn, task_id, "completed")
            return "compiled"
        compiler_error = compile_result.stderr
    _mark_generation_blocked(conn, task_id, max_retries, compiler_error or "\n".join(validation_errors))
    return "compile_failed"


def _controller_has_business_logic(source: str) -> bool:
    without_handlers = re.sub(r"@ExceptionHandler[\s\S]*?(?=\n\s*@|\n})", "", source)
    forbidden_logic = [r"\bJdbcTemplate\b", r"\.query\s*\(", r"\bif\s*\(", r"\bfor\s*\(", r"\bwhile\s*\(", r"\bswitch\s*\("]
    return any(re.search(pattern, without_handlers) for pattern in forbidden_logic)


def _mvn_compile(project_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["mvn", "compile"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _mark_generation_blocked(
    conn: sqlite3.Connection,
    task_id: str,
    attempt_number: int,
    error_message: str,
) -> None:
    conn.execute(
        """
        UPDATE agent_tasks
        SET status = 'blocked',
            blocking_reason = 'compile_failed',
            attempt_number = ?,
            error_message = ?,
            updated_at = ?
        WHERE task_id = ?
        """,
        (attempt_number, error_message, utc_now(), task_id),
    )
    conn.commit()


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def _find_suffix(files: dict[str, str], suffix: str) -> str | None:
    normalized_suffix = _normalize_path(suffix)
    return next((path for path in files if path.endswith(normalized_suffix)), None)


java_service_generation_agent = LlmAgent(
    name="JavaServiceGenerationAgent",
    description="Generates and compiles a pilot Spring Boot microservice for one assembled operation.",
    model=AGENT_MODEL,
    instruction=JAVA_SERVICE_GENERATION_INSTRUCTION,
    tools=[parse_generated_project_output, validate_generated_project, write_generated_project],
)
