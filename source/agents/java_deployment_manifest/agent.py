from __future__ import annotations

from copy import deepcopy
import constants
import json
import re
import sqlite3
from pathlib import Path
from runtime.project_paths import project_root
from typing import Callable

from constants import AGENT_MODEL, MAX_AGENT_TASK_RETRIES, OUTPUT_ROOT, TEMPLATES_ROOT
from models.common_models import TargetLanguage
from models.deployment_models import DeploymentSpec, DeploymentTemplateRef, RenderedManifest
from tools.deployment_tools.template_renderer import render_manifest
from tools.state_store_tools._json import dumps, utc_now
from tools.state_store_tools.agent_tasks import get_agent_task, update_task_status
from tools.state_store_tools.generated_artifacts import upsert_generated_artifact

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


DEPLOYMENT_VALUES_INSTRUCTION = """
You are providing configuration values for a deployment manifest.
Do NOT write YAML. Output ONLY a JSON object with these keys:

OPERATION_ID: {operation_id}
SERVICE_CLASS: {service_class_name}
SPRING_PORT: {port}
DB_LOOKUPS: {db_lookup_count}
IMAGE_NAME_HINT: {image_name_hint}

Output JSON with service_name, image_name, container_port, env_vars, health_paths,
requires_db, and replicas.
"""


ValuesProvider = Callable[[str | None], str | dict]


def parse_deployment_values(output: str | dict) -> dict:
    """Parse deployment-value JSON supplied by the manifest agent."""
    if isinstance(output, dict):
        values = output
    else:
        text = output.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        values = json.loads(text)
    if not isinstance(values, dict):
        raise ValueError("Deployment values must be a JSON object")
    return values


def build_deployment_spec(
    operation_id: str,
    values: dict,
    *,
    template_dir: str,
    platform: str = constants.DEPLOYMENT_PLATFORM,
    environment: str = constants.DEPLOYMENT_ENVIRONMENT,
) -> DeploymentSpec:
    """Build a deployment spec from agent-provided values."""
    service_name = values.get("service_name") or f"{operation_id.lower()}-service"
    return DeploymentSpec(
        operation_id=operation_id,
        service_name=service_name,
        target_language=TargetLanguage.java,
        image_name=values.get("image_name") or service_name,
        port=int(values.get("container_port", constants.DEPLOYMENT_CONTAINER_PORT)),
        health_paths=values.get("health_paths", deepcopy(constants.DEPLOYMENT_HEALTH_PATHS)),
        env_vars=values.get("env_vars", deepcopy(constants.DEPLOYMENT_ENV_VARS)),
        template_ref=DeploymentTemplateRef(
            platform=platform,
            template_dir=template_dir,
            defaults_path="",
            environment=environment,
        ),
        platform=platform,
    )


def run_java_deployment_manifest_agent(
    conn: sqlite3.Connection,
    task_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    values_provider: ValuesProvider,
    *,
    template_dir: str | None = None,
    output_root: str = str(project_root() / OUTPUT_ROOT),
) -> RenderedManifest:
    """Generate deployment manifests from values, templates, and store state."""
    task = get_agent_task(conn, task_id)
    max_retries = int(task["max_retries"] or MAX_AGENT_TASK_RETRIES) if task else MAX_AGENT_TASK_RETRIES
    templates = template_dir or str(project_root() / TEMPLATES_ROOT / "deployment")
    error_message = None
    for attempt in range(1, max_retries + 1):
        try:
            values = parse_deployment_values(values_provider(error_message))
            spec = build_deployment_spec(operation_id, values, template_dir=templates)
            manifest = render_manifest(templates, spec)
        except (json.JSONDecodeError, ValueError) as exc:
            error_message = str(exc)
            continue
        output_path = _write_manifest_files(manifest, output_root, channel, operation_id)
        upsert_generated_artifact(
            conn,
            artifact_id=f"{run_id}:deployment_manifest:{operation_id}:{task_id}",
            run_id=run_id,
            operation_id=operation_id,
            channel=channel,
            target_language="java",
            artifact_kind="deployment_manifest",
            generated_path=str(output_path),
            status="converted",
            blocking_reason=None,
            attempt_number=attempt,
        )
        if task:
            update_task_status(conn, task_id, "completed")
        return manifest
    _mark_manifest_blocked(conn, task_id, max_retries, error_message or "deployment manifest generation failed")
    raise ValueError(error_message or "deployment manifest generation failed")


def _write_manifest_files(
    manifest: RenderedManifest,
    output_root: str,
    channel: str,
    operation_id: str,
) -> Path:
    manifest_root = Path(output_root) / channel / operation_id / "deployment"
    manifest_root.mkdir(parents=True, exist_ok=True)
    for filename, content in manifest.files.items():
        (manifest_root / filename).write_text(content, encoding="utf-8")
    return manifest_root


def _mark_manifest_blocked(
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


java_deployment_manifest_agent = LlmAgent(
    name="JavaDeploymentManifestAgent",
    description="Renders Java microservice deployment manifests from values and templates.",
    model=AGENT_MODEL,
    instruction=DEPLOYMENT_VALUES_INSTRUCTION,
    tools=[parse_deployment_values, build_deployment_spec, render_manifest],
)
