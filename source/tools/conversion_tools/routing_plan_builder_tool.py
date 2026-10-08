from __future__ import annotations

import logging
import re
import sqlite3

from models.conversion_models import ClosureStatus, OperationClosure, RoutingPlan, RoutingStep
from tools.state_store_tools._json import loads
from tools.state_store_tools.operation_closures import get_operation_closure
from tools.state_store_tools.routing_plans import upsert_routing_plan


LOGGER = logging.getLogger(__name__)


def build_routing_plan(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> RoutingPlan:
    """Build and store a routing plan from a READY operation closure."""
    closure = _ready_closure(conn, operation_id, channel, run_id)
    step_indices = {step_id: index for index, step_id in enumerate(closure.included_opstep_ids)}
    steps = []
    for step_id in closure.included_opstep_ids:
        opstep_metadata = _opstep_metadata(conn, run_id, step_id)
        steps.append(
            RoutingStep(
                step_id=step_id,
                step_index=step_indices[step_id],
                impl_class=str(opstep_metadata.get("impl_class") or ""),
                parameters=dict(opstep_metadata.get("parameters", {})),
                transitions=_resolved_transitions(
                    closure.routing_graph.get(step_id, {}),
                    step_indices,
                    step_id,
                ),
                return_body_switches=dict(closure.return_body_switches),
            )
        )
    _warn_unreachable_steps(closure.included_opstep_ids, steps)
    plan = RoutingPlan(
        operation_id=operation_id,
        channel=channel,
        steps=steps,
        has_finally_step=any(step.step_id.lower().endswith("finally") for step in steps),
    )
    upsert_routing_plan(
        conn,
        operation_id=operation_id,
        channel=channel,
        run_id=run_id,
        plan=plan.model_dump(mode="json"),
        status="ready",
    )
    return plan


def _ready_closure(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> OperationClosure:
    row = get_operation_closure(conn, operation_id, channel, run_id)
    if row is None or not row.get("closure_json"):
        raise KeyError(f"Operation closure not found: {operation_id}/{channel}/{run_id}")
    closure = OperationClosure(**row["closure_json"])
    if closure.status != ClosureStatus.READY:
        raise ValueError(f"Operation closure is not READY: {closure.status}")
    return closure


def _opstep_metadata(conn: sqlite3.Connection, run_id: str, step_id: str) -> dict:
    row = conn.execute(
        """
        SELECT metadata_json FROM source_artifacts
        WHERE run_id = ? AND kind = 'opStep' AND logical_id = ?
        """,
        (run_id, step_id),
    ).fetchone()
    return loads(row["metadata_json"], {}) if row else {}


def _resolved_transitions(
    transitions: dict[str, str],
    step_indices: dict[str, int],
    step_id: str,
) -> dict[str, int | str]:
    resolved: dict[str, int | str] = {}
    for raw_key, raw_target in transitions.items():
        key = _transition_key(raw_key)
        target = str(raw_target)
        if target in step_indices:
            resolved[key] = step_indices[target]
        elif target.lower() in {"end", "next"}:
            resolved[key] = target.lower()
        else:
            LOGGER.warning("Unresolved routing target from %s: %s", step_id, target)
            resolved[key] = target
    return resolved


def _transition_key(raw_key: str) -> str:
    key = str(raw_key)
    match = re.fullmatch(r"on(-?\d+)Do", key)
    if match:
        return match.group(1)
    if key == "onOtherDo":
        return "other"
    if key == "onTimeoutDo":
        return "timeout"
    return key


def _warn_unreachable_steps(step_ids: list[str], steps: list[RoutingStep]) -> None:
    if not steps:
        return
    reachable = {0}
    pending = [0]
    while pending:
        current = pending.pop()
        for target in steps[current].transitions.values():
            next_index = _reachable_index(target, current, len(steps))
            if next_index is not None and next_index not in reachable:
                reachable.add(next_index)
                pending.append(next_index)
    for index, step_id in enumerate(step_ids):
        if index not in reachable:
            LOGGER.warning("Unreachable routing step: %s", step_id)


def _reachable_index(target: int | str, current_index: int, step_count: int) -> int | None:
    if isinstance(target, int):
        return target
    if target == "next" and current_index + 1 < step_count:
        return current_index + 1
    return None
