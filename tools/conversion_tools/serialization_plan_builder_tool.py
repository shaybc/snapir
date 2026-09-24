from __future__ import annotations

import sqlite3

from models.conversion_models import (
    BuildStep,
    ClosureStatus,
    OperationClosure,
    ParseStep,
    SerializationPlan,
)
from tools.state_store_tools.operation_closures import get_operation_closure
from tools.state_store_tools.serialization_plans import upsert_serialization_plan


def build_serialization_plan(
    conn: sqlite3.Connection,
    operation_id: str,
    channel: str,
    run_id: str,
    vault_root: str,
) -> SerializationPlan:
    """Build and store request/response serialization plans from a READY closure."""
    closure = _ready_closure(conn, operation_id, channel, run_id)
    context_types = {field.name: field.inferred_type for field in closure.context_fields}
    request_fields = _service_layer_fields(conn, closure.ref_formats.get("csRequestFormat"), channel, run_id)
    reply_fields = _service_layer_fields(conn, closure.ref_formats.get("csReplyFormat"), channel, run_id)
    error_fields = _service_layer_fields(conn, closure.ref_formats.get("csErrorReplyFormat"), channel, run_id)
    plan = SerializationPlan(
        operation_id=operation_id,
        channel=channel,
        request_parsing=[
            ParseStep(
                field_name=field_name,
                xml_path=field_name,
                context_field=field_name,
                decorator_chain=list(reversed(_decorator_chain(closure, field_name))),
                java_type=context_types.get(field_name, "String"),
            )
            for field_name in request_fields
            if field_name not in _db_lookup_fields(closure)
        ],
        response_building=[
            _build_step(closure, field_name)
            for field_name in reply_fields
            if field_name not in _db_lookup_fields(closure)
        ],
        error_response_building=[
            _build_step(closure, field_name)
            for field_name in error_fields
            if field_name not in _db_lookup_fields(closure)
        ],
        db_lookups=closure.formats.db_lookups,
    )
    upsert_serialization_plan(
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


def _service_layer_fields(
    conn: sqlite3.Connection,
    format_id: str | None,
    channel: str,
    run_id: str,
) -> list[str]:
    if not format_id:
        return []
    row = conn.execute(
        """
        SELECT requirements_json FROM service_layer_requirements
        WHERE format_id = ? AND channel = ? AND run_id = ?
        """,
        (format_id, channel, run_id),
    ).fetchone()
    if row is None or not row["requirements_json"]:
        return []
    from tools.state_store_tools._json import loads

    requirements = loads(row["requirements_json"], {}) or {}
    fields = [item["field_name"] for item in requirements.get("field_transformations", [])]
    fields.extend(item["field_name"] for item in requirements.get("db_lookups", []))
    return list(dict.fromkeys(fields))


def _build_step(closure: OperationClosure, field_name: str) -> BuildStep:
    chain = _decorator_chain(closure, field_name)
    return BuildStep(
        field_name=field_name,
        context_field=field_name,
        xml_element=field_name,
        decorator_chain=chain,
        nullable="nilDecorator" in chain,
    )


def _decorator_chain(closure: OperationClosure, field_name: str) -> list[str]:
    prefix = f"{field_name}/"
    for formatter_id, decorators in closure.formats.decorator_chains.items():
        if formatter_id.startswith(prefix):
            return list(decorators)
    return []


def _db_lookup_fields(closure: OperationClosure) -> set[str]:
    return {lookup.field_name for lookup in closure.formats.db_lookups}
