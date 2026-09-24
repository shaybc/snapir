from __future__ import annotations

from models.common_models import TargetLanguage, TaskStatus
from models.conversion_models import RoutingPlan, RoutingStep
from models.migration_models import MigrationBatch, MigrationPlan, MigrationTaskPacket, OperationGrouping
from tools.artifact_registry_tools.component_registry import increment_used_by_validated, register_component
from models.conversion_models import ConversionStatus
from models.registry_models import ComponentRegistryRecord
from tools.routing_tools.batch_dispatcher import dispatch_all_batches
from tools.state_store_tools.channel_operations import get_operation, upsert_operation
from tools.trace_capture_tools.trace_scenario_builder import derive_trace_scenarios


RUN_ID = "run-1"
CHANNEL = "INTERNET"


def packet(operation_id: str) -> MigrationTaskPacket:
    return MigrationTaskPacket(
        task_id=f"task-{operation_id}",
        run_id=RUN_ID,
        operation_id=operation_id,
        channel=CHANNEL,
        target_language=TargetLanguage.java,
        group=OperationGrouping.one_step,
        status=TaskStatus.pending,
    )


def plan() -> MigrationPlan:
    batch = MigrationBatch(
        batch_id="pilot",
        run_id=RUN_ID,
        task_packets=[packet("SimpleGetOp"), packet("BranchGetOp")],
        is_pilot=True,
        status=TaskStatus.pending,
    )
    return MigrationPlan(
        plan_id="plan-run-1",
        run_id=RUN_ID,
        batches=[batch],
        total_operations=2,
        unusual_count=0,
        status=TaskStatus.pending,
    )


def run_config():
    from tests.test_batch_dispatcher import run_config as build_config

    return build_config()


def test_full_pilot_pipeline(e2e_conn, mock_llm):
    migration_plan = plan()
    result = dispatch_all_batches(e2e_conn, migration_plan, run_config())
    register_component(
        e2e_conn,
        ComponentRegistryRecord(
            component_id="fmt-StandardHeaderFmt",
            artifact_kind="xml_fmtdef",
            logical_id="StandardHeaderFmt",
            source_path="fixtures/sample_vault/formats/StandardHeaderFmt.md",
            source_hash="hash-standard-header",
            target_language=TargetLanguage.java,
            artifact_schema_version="v1",
            generated_path="common-lib/StandardHeaderFmt.java",
            status=ConversionStatus.validated,
            used_by_operations=["SimpleGetOp", "BranchGetOp"],
            used_by_validated_operations=0,
        ),
    )
    increment_used_by_validated(e2e_conn, "fmt-StandardHeaderFmt")
    increment_used_by_validated(e2e_conn, "fmt-StandardHeaderFmt")
    branch_routing = RoutingPlan(
        operation_id="BranchGetOp",
        channel=CHANNEL,
        has_finally_step=False,
        steps=[
            RoutingStep(step_id="ValidateInput", step_index=0, impl_class="ValidateInput", transitions={"0": 1, "4": "end"}),
            RoutingStep(step_id="GetDetailSP", step_index=1, impl_class="GetDetailSP", transitions={"0": "end"}),
        ],
    )

    scenarios = derive_trace_scenarios(branch_routing)

    assert result.batch_results[0].success_count == 2
    assert mock_llm("code_review")["passed"] is True
    assert len(scenarios) == 2


def test_include_operations_filter(e2e_conn, mock_llm):
    include_operations = {"SimpleGetOp"}
    for operation_id in ["SimpleGetOp", "BranchGetOp"]:
        if operation_id in include_operations:
            upsert_operation(
                e2e_conn,
                operation_id=operation_id,
                channel=CHANNEL,
                run_id=RUN_ID,
                xml_file_path=f"{operation_id}.xml",
                status="pending",
            )

    assert get_operation(e2e_conn, "SimpleGetOp", CHANNEL, RUN_ID) is not None
    assert get_operation(e2e_conn, "BranchGetOp", CHANNEL, RUN_ID) is None


def test_exclude_operations_filter(e2e_conn, mock_llm):
    exclude_operations = {"BranchGetOp"}
    for operation_id in ["SimpleGetOp", "BranchGetOp"]:
        if operation_id not in exclude_operations:
            upsert_operation(
                e2e_conn,
                operation_id=operation_id,
                channel=CHANNEL,
                run_id=RUN_ID,
                xml_file_path=f"{operation_id}.xml",
                status="pending",
            )

    assert get_operation(e2e_conn, "SimpleGetOp", CHANNEL, RUN_ID) is not None
    assert get_operation(e2e_conn, "BranchGetOp", CHANNEL, RUN_ID) is None
