from __future__ import annotations

from models.conversion_models import (
    ClosureStatus,
    ContextField,
    DbLookupRequirement,
    FormatSet,
    OperationClosure,
    ServiceLayerRequirements,
    FieldTransformation,
)
from tools.conversion_tools.context_plan_builder_tool import build_context_plan
from tools.conversion_tools.routing_plan_builder_tool import build_routing_plan
from tools.conversion_tools.serialization_plan_builder_tool import build_serialization_plan
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.operation_closures import upsert_operation_closure
from tools.state_store_tools.serialization_plans import upsert_serialization_plan
from tools.state_store_tools.service_layer_requirements import upsert_service_layer_requirements
from tools.state_store_tools.source_artifacts import upsert_source_artifact


RUN_ID = "run-1"


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def context_field(name: str, java_type: str = "String", written_by: list[str] | None = None) -> ContextField:
    return ContextField(
        name=name,
        context_level="ContextA",
        source="formatter",
        inferred_type=java_type,
        inherited=False,
        written_by=written_by or [],
    )


def ready_closure(*, included: list[str] | None = None, routing_graph: dict | None = None) -> OperationClosure:
    return OperationClosure(
        operation_id="OpA",
        channel="INTERNET",
        run_id=RUN_ID,
        status=ClosureStatus.READY,
        source_xml_path="ops/OpA.xml",
        operation_fields="Host=abc,Mode=fast",
        ini_values=["TraceId=seed"],
        ref_formats={
            "csRequestFormat": "RequestFmt",
            "csReplyFormat": "ReplyFmt",
            "csErrorReplyFormat": "ErrorFmt",
        },
        return_body_switches={"4": "ErrorFmt"},
        included_opstep_ids=included or ["StepA", "StepB"],
        routing_graph=routing_graph or {"StepA": {"on0Do": "StepB"}, "StepB": {"on0Do": "end"}},
        java_classes=[],
        formats=FormatSet(
            request_format_id="RequestFmt",
            reply_format_id="ReplyFmt",
            error_reply_format_id="ErrorFmt",
            all_format_ids=["RequestFmt", "ReplyFmt", "ErrorFmt"],
            decorator_chains={
                "ClientId/CCString": ["TrimDecorator", "PadDecorator"],
                "ReplyCode/CCString": ["nilDecorator"],
                "ErrorCode/CCString": ["PadDecorator"],
            },
            db_lookups=[
                DbLookupRequirement(
                    field_name="BranchName",
                    from_table="BRANCH",
                    from_column="NAME",
                    key_value_field="BranchId",
                )
            ],
        ),
        context_id="ContextA",
        context_chain=["ContextA"],
        context_fields=[
            context_field("ClientId"),
            context_field("ReplyCode"),
            context_field("ErrorCode"),
            context_field("BranchName"),
            context_field("StepWritten", written_by=["StepA"]),
        ],
        source_hash_composite="hash",
    )


def store_closure(conn, closure: OperationClosure):
    upsert_operation_closure(
        conn,
        operation_id=closure.operation_id,
        channel=closure.channel,
        run_id=closure.run_id,
        status=closure.status.value,
        closure=closure.model_dump(mode="json"),
        source_hash_composite=closure.source_hash_composite,
    )


def add_opstep(conn, step_id: str, impl_class: str = "com.bank.Step"):
    upsert_source_artifact(
        conn,
        artifact_id=f"{RUN_ID}:opStep:{step_id}",
        run_id=RUN_ID,
        kind="opStep",
        logical_id=step_id,
        metadata={
            "id": step_id,
            "impl_class": impl_class,
            "parameters": {"input": step_id},
        },
    )


def add_service_layer_requirements(conn):
    for format_id, fields in {
        "RequestFmt": ["ClientId", "BranchName"],
        "ReplyFmt": ["ReplyCode"],
        "ErrorFmt": ["ErrorCode"],
    }.items():
        slr = ServiceLayerRequirements(
            format_id=format_id,
            channel="INTERNET",
            field_transformations=[
                FieldTransformation(field_name=field, format_direction=[], unformat_direction=[])
                for field in fields
            ],
            db_lookups=[
                DbLookupRequirement(
                    field_name="BranchName",
                    from_table="BRANCH",
                    from_column="NAME",
                    key_value_field="BranchId",
                )
            ] if format_id == "RequestFmt" else [],
        )
        upsert_service_layer_requirements(
            conn,
            format_id=format_id,
            channel="INTERNET",
            run_id=RUN_ID,
            requirements=slr.model_dump(mode="json"),
            status="ready",
        )


def test_routing_plan_resolves_named_targets_to_step_index():
    conn = memory_conn()
    closure = ready_closure()
    store_closure(conn, closure)
    add_opstep(conn, "StepA")
    add_opstep(conn, "StepB")

    plan = build_routing_plan(conn, "OpA", "INTERNET", RUN_ID)

    assert plan.steps[0].transitions["0"] == 1
    assert plan.steps[1].transitions["0"] == "end"
    assert plan.steps[0].parameters == {"input": "StepA"}


def test_routing_plan_logs_unreachable_step_without_error(caplog):
    conn = memory_conn()
    closure = ready_closure(
        included=["StepA", "StepB", "StepC"],
        routing_graph={"StepA": {"on0Do": "end"}, "StepB": {"on0Do": "end"}, "StepC": {"on0Do": "end"}},
    )
    store_closure(conn, closure)
    for step_id in closure.included_opstep_ids:
        add_opstep(conn, step_id)

    with caplog.at_level("WARNING"):
        plan = build_routing_plan(conn, "OpA", "INTERNET", RUN_ID)

    assert len(plan.steps) == 3
    assert "Unreachable routing step: StepB" in caplog.text
    assert "Unreachable routing step: StepC" in caplog.text


def test_context_plan_init_sequence_orders_request_dto_before_operation_fields():
    conn = memory_conn()
    closure = ready_closure()
    store_closure(conn, closure)
    upsert_serialization_plan(
        conn,
        operation_id="OpA",
        channel="INTERNET",
        run_id=RUN_ID,
        plan={
            "operation_id": "OpA",
            "channel": "INTERNET",
            "request_parsing": [{"context_field": "ClientId"}],
        },
        status="ready",
    )

    plan = build_context_plan(conn, "OpA", "INTERNET", RUN_ID)

    assert [entry.source for entry in plan.init_sequence[:3]] == [
        "request_dto",
        "operation_fields",
        "operation_fields",
    ]
    assert plan.init_sequence[0].field_name == "ClientId"


def test_serialization_plan_reverses_parse_decorator_chain_and_excludes_db_lookup():
    conn = memory_conn()
    closure = ready_closure()
    store_closure(conn, closure)
    add_service_layer_requirements(conn)

    plan = build_serialization_plan(conn, "OpA", "INTERNET", RUN_ID, vault_root="unused")

    assert [step.context_field for step in plan.request_parsing] == ["ClientId"]
    assert plan.request_parsing[0].decorator_chain == ["PadDecorator", "TrimDecorator"]
    assert plan.db_lookups[0].field_name == "BranchName"


def test_serialization_plan_build_step_uses_forward_chain_and_nullable_nil_decorator():
    conn = memory_conn()
    closure = ready_closure()
    store_closure(conn, closure)
    add_service_layer_requirements(conn)

    plan = build_serialization_plan(conn, "OpA", "INTERNET", RUN_ID, vault_root="unused")

    assert plan.response_building[0].context_field == "ReplyCode"
    assert plan.response_building[0].decorator_chain == ["nilDecorator"]
    assert plan.response_building[0].nullable is True
    assert plan.error_response_building[0].decorator_chain == ["PadDecorator"]
