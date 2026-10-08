from __future__ import annotations

import sqlite3

from models.conversion_models import (
    ClosureStatus,
    ContextPlan,
    ContextPlanField,
    InitEntry,
    OperationClosure,
)
from tools.state_store_tools.context_plans import upsert_context_plan
from tools.state_store_tools.operation_closures import get_operation_closure


def build_context_plan(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
) -> ContextPlan:
    """Build and store a context initialization plan from a READY closure."""
    closure = _ready_closure(conn, operation_id, channel, run_id)
    request_fields = _request_dto_fields(conn, operation_id, channel, run_id)
    init_sequence = [
        InitEntry(field_name=field_name, source="request_dto", value_or_expression=field_name)
        for field_name in request_fields
    ]
    init_sequence.extend(_operation_field_entries(closure.operation_fields))
    init_sequence.extend(_ini_value_entries(closure.ini_values))
    fields = [
        ContextPlanField(
            name=field.name,
            java_type=field.inferred_type,
            context_level=field.context_level,
            initialized_from="opstep_write" if field.written_by else "request_dto",
            initialized_by=",".join(field.written_by) if field.written_by else None,
        )
        for field in closure.context_fields
    ]
    plan = ContextPlan(
        operation_id=operation_id,
        channel=channel,
        context_class=closure.context_id,
        fields=fields,
        init_sequence=init_sequence,
    )
    upsert_context_plan(
        conn,
        operation_id=operation_id,
        channel=channel,
        run_id=run_id,
        plan=plan.model_dump(mode="json"),
        status="ready",
    )
    return plan


def _ready_closure(conn: sqlite3.Connection, operation_id: str, channel: str, run_id: str) -> OperationClosure:
    row = get_operation_closure(conn, operation_id, channel, run_id)
    if row is None or not row.get("closure_json"):
        raise KeyError(f"Operation closure not found: {operation_id}/{channel}/{run_id}")
    closure = OperationClosure(**row["closure_json"])
    if closure.status != ClosureStatus.READY:
        raise ValueError(f"Operation closure is not READY: {closure.status}")
    return closure


def _request_dto_fields(conn: sqlite3.Connection, operation_id: str, channel: str, run_id: str) -> list[str]:
    row = conn.execute(
        """
        SELECT plan_json FROM serialization_plans
        WHERE operation_id = ? AND channel = ? AND run_id = ?
        """,
        (operation_id, channel, run_id),
    ).fetchone()
    if row is None or not row["plan_json"]:
        return []
    from tools.state_store_tools._json import loads

    plan = loads(row["plan_json"], {}) or {}
    return [step["context_field"] for step in plan.get("request_parsing", [])]


def _operation_field_entries(operation_fields: str | None) -> list[InitEntry]:
    entries = []
    if not operation_fields:
        return entries
    for item in operation_fields.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        entries.append(
            InitEntry(
                field_name=key.strip(),
                source="operation_fields",
                value_or_expression=value.strip(),
            )
        )
    return entries


def _ini_value_entries(ini_values: list[str]) -> list[InitEntry]:
    entries = []
    for value in ini_values:
        if "=" in value:
            key, expression = value.split("=", 1)
            field_name = key.strip()
            value_or_expression = expression.strip()
        else:
            field_name = value.strip()
            value_or_expression = value.strip()
        if field_name:
            entries.append(
                InitEntry(
                    field_name=field_name,
                    source="ini_value",
                    value_or_expression=value_or_expression,
                )
            )
    return entries
