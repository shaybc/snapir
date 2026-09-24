from __future__ import annotations

from pathlib import Path

import pytest

from agents.java_deployment_manifest.agent import (
    build_deployment_spec,
    run_java_deployment_manifest_agent,
)
from tools.deployment_tools.template_renderer import render_manifest
from tools.state_store_tools.agent_tasks import get_agent_task, upsert_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.generated_artifacts import get_generated_artifact


RUN_ID = "run-1"
TASK_ID = "task-manifest"
OPERATION_ID = "TransferFunds"
CHANNEL = "INTERNET"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def add_task(conn, max_retries: int = 3):
    upsert_agent_task(
        conn,
        task_id=TASK_ID,
        run_id=RUN_ID,
        agent_name="JavaDeploymentManifestAgent",
        scope_type="operation",
        scope_id=OPERATION_ID,
        channel=CHANNEL,
        target_language="java",
        status="pending",
        max_retries=max_retries,
    )


def write_templates(root: Path):
    root.mkdir(parents=True)
    (root / "deployment.yaml.j2").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {{ spec.service_name }}\n",
        encoding="utf-8",
    )
    (root / "service.yaml.j2").write_text(
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: {{ spec.service_name }}\n",
        encoding="utf-8",
    )


def values():
    return {
        "service_name": "transfer-funds",
        "image_name": "registry/transfer-funds:latest",
        "container_port": 8080,
        "env_vars": {"SPRING_PROFILES_ACTIVE": "prod"},
        "health_paths": {"liveness": "/actuator/health", "readiness": "/actuator/health"},
        "requires_db": True,
        "replicas": 1,
    }


def test_rendered_deployment_contains_service_name_from_values(tmp_path: Path):
    template_dir = tmp_path / "templates"
    write_templates(template_dir)
    spec = build_deployment_spec(OPERATION_ID, values(), template_dir=str(template_dir))

    manifest = render_manifest(str(template_dir), spec)

    assert "name: transfer-funds" in manifest.files["deployment.yaml"]


def test_invalid_yaml_in_template_raises_before_delivery(tmp_path: Path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "deployment.yaml.j2").write_text("apiVersion: [broken\n", encoding="utf-8")
    spec = build_deployment_spec(OPERATION_ID, values(), template_dir=str(template_dir))

    with pytest.raises(ValueError, match="Invalid rendered YAML"):
        render_manifest(str(template_dir), spec)


def test_llm_json_parse_failure_retries(tmp_path: Path):
    conn = memory_conn()
    add_task(conn)
    template_dir = tmp_path / "templates"
    write_templates(template_dir)
    outputs = ["not json", values()]

    manifest = run_java_deployment_manifest_agent(
        conn,
        TASK_ID,
        OPERATION_ID,
        CHANNEL,
        RUN_ID,
        lambda error: outputs.pop(0),
        template_dir=str(template_dir),
        output_root=str(tmp_path / "out"),
    )

    task = get_agent_task(conn, TASK_ID)
    artifact = get_generated_artifact(conn, f"{RUN_ID}:deployment_manifest:{OPERATION_ID}:{TASK_ID}")
    assert manifest.validated is True
    assert task["status"] == "completed"
    assert artifact["status"] == "converted"
    assert outputs == []
