from __future__ import annotations

import json
import sqlite3
from urllib.error import URLError
from urllib.request import Request, urlopen

from models.validation_models import ExecutionTrace
from tools.state_store_tools.execution_traces import insert_execution_trace
from tools.trace_capture_tools.trace_scenario_builder import TraceScenario


class LegacyTraceUnavailableError(RuntimeError):
    """Raised when the legacy trace interceptor endpoint cannot be reached."""


def capture_legacy_trace(
    legacy_base_url: str,
    operation_id: str,
    channel: str,
    scenario: TraceScenario,
    conn: sqlite3.Connection | None = None,
    run_id: str | None = None,
) -> ExecutionTrace:
    """Capture a trace from a legacy WSBCC TraceInterceptorServlet."""
    try:
        _post_legacy_request(legacy_base_url, operation_id, channel, scenario.request_xml_template)
        trace_json = _get_latest_trace(legacy_base_url, operation_id)
    except URLError as exc:
        raise LegacyTraceUnavailableError(str(exc)) from exc
    trace = ExecutionTrace(**trace_json)
    if conn and run_id:
        insert_execution_trace(
            conn,
            trace_id=f"{run_id}:legacy:{operation_id}:{scenario.name}",
            operation_id=operation_id,
            channel=channel,
            run_id=run_id,
            target="legacy",
            scenario=scenario.name,
            trace=trace.model_dump(mode="json"),
        )
    return trace


def _post_legacy_request(base_url: str, operation_id: str, channel: str, request_xml: str) -> None:
    request = Request(
        f"{base_url.rstrip('/')}/{channel}/{operation_id}",
        data=request_xml.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/xml"},
    )
    with urlopen(request, timeout=30):
        return


def _get_latest_trace(base_url: str, operation_id: str) -> dict:
    with urlopen(f"{base_url.rstrip('/')}/trace/{operation_id}/latest", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


# TraceInterceptorServlet interface contract:
# - Deployed alongside the legacy WSBCC runtime.
# - Wraps CCDSEServerOperation.execute(operationName, requestXml).
# - Records steps_executed with return code and context writes per step.
# - Records selected_reply_format, reply_format_switched, switch_triggered_by, and final_xml.
# - Exposes GET /trace/{operationName}/latest as ExecutionTrace-compatible JSON.
