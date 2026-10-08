from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from runtime.java_toolchain import run_java, java_version
from pathlib import Path
from urllib.request import Request, urlopen

from models.validation_models import ExecutionTrace
from tools.state_store_tools.execution_traces import insert_execution_trace
from tools.trace_capture_tools.trace_scenario_builder import TraceScenario


def enable_trace_interceptor(
    service_project_path: str,
    operation_id: str,
) -> None:
    """Copy the generated-service trace aspect into a Spring Boot project and compile it."""
    project_root = Path(service_project_path)
    package_root = project_root / "src" / "main" / "java"
    trace_dir = next(package_root.rglob("service"), package_root) / "trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    template_path = Path(__file__).with_name("ExecutionTraceInterceptor.java.template")
    target_path = trace_dir / "ExecutionTraceInterceptor.java"
    content = template_path.read_text(encoding="utf-8").replace("${operationId}", operation_id)
    target_path.write_text(content, encoding="utf-8")
    run_java(["mvn", "compile"], cwd=project_root, capture_output=True, text=True, check=False)


def read_generated_trace(
    operation_id: str,
    scenario: TraceScenario,
    service_base_url: str,
    conn: sqlite3.Connection | None = None,
    run_id: str | None = None,
    channel: str = "",
) -> ExecutionTrace:
    """Invoke the generated service and read its local trace JSON file."""
    request = Request(
        service_base_url.rstrip("/"),
        data=scenario.request_xml_template.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/xml"},
    )
    with urlopen(request, timeout=30):
        pass
    trace_path = Path("/tmp") / f"trace_{operation_id}.json"
    trace = ExecutionTrace(**json.loads(trace_path.read_text(encoding="utf-8")))
    if conn and run_id:
        insert_execution_trace(
            conn,
            trace_id=f"{run_id}:generated:{operation_id}:{scenario.name}",
            operation_id=operation_id,
            channel=channel,
            run_id=run_id,
            target="generated",
            scenario=scenario.name,
            target_language="java",
            trace=trace.model_dump(mode="json"),
        )
    return trace
