"""Generate and validate migration plans using existing planning tools."""

import json

from agents.migration_planning.agent import PLANNING_INSTRUCTION, write_migration_plan
from agents.migration_planning.plan_validator import validate_migration_plan
from models.migration_models import MigrationPlan
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.mock_executor import MockExecutor


def prepare_plan(conn, config, profile, operations) -> MigrationPlan:
    """Produce a validated plan, preserving channel identities and run ownership."""
    if profile.conversion_strategy == 'behavior_units':
        from tools.operation_call_tools.preflight import require_preflight_passed
        require_preflight_passed(conn, config.run_id)
        from runtime.intake_plan import dependency_plan_context
        context = dependency_plan_context(conn, config.run_id)
        if context:
            by_key = {item['channel'] + '/' + item['operation_id']: item for item in operations}
            dependencies = {item['operation']: item for item in context['operations']}
            operations = [dict(by_key[key], operation_dependencies=dependencies[key]) for key in context['order']]
    if not operations:
        raise ValueError("Conversion scope contains no operations")
    if profile.model_provider == "mock":
        packets = [dict(task_id=f"{config.run_id}:{item['channel']}:{item['operation_id']}",
                        run_id=config.run_id, operation_id=item["operation_id"], channel=item["channel"],
                        target_language="java", group="one_step", status="pending") for item in operations]
        batches = [dict(batch_id=f"{config.run_id}:batch:{index}", run_id=config.run_id,
                        task_packets=packets[offset:offset + config.max_operations_per_batch],
                        is_pilot=index == 0, status="pending")
                   for index, offset in enumerate(range(0, len(packets), config.max_operations_per_batch))]
        response = json.dumps(dict(plan_id=f"{config.run_id}:plan", run_id=config.run_id,
                                  batches=batches, total_operations=len(packets), unusual_count=0, status="pending"))
        executor = MockExecutor(response)
    else:
        executor = AdkExecutor(profile)
    instruction = PLANNING_INSTRUCTION.replace("{max_ops_per_batch}", str(config.max_operations_per_batch))
    instruction += "\nFor a scope smaller than three operations, include the whole scope in the pilot."
    if any(item.get('operation_dependencies') for item in operations):
        instruction += '\nRespect operation_dependencies: schedule lower build waves before their callers. Keep each circular group together and flag unresolved dependencies; do not infer that shared classes are operation calls.'
    if profile.conversion_strategy == 'behavior_units' and context:
        instruction += '\nThe supplied operation order is mandatory across and within batches. Do not move a pilot or unusual operation ahead of a prerequisite. Cycles have already been blocked by intake.'
    payload = json.dumps(dict(run_id=config.run_id, operations=operations, schema=MigrationPlan.model_json_schema()))
    plan = MigrationPlan.model_validate_json(executor.execute(instruction, payload))
    packets = [packet for batch in plan.batches for packet in batch.task_packets]
    if plan.run_id != config.run_id or any(batch.run_id != config.run_id for batch in plan.batches):
        raise ValueError("Plan has incorrect run ownership")
    if any(packet.run_id != config.run_id or packet.target_language.value != "java" for packet in packets):
        raise ValueError("Plan task has incorrect run ownership or target language")
    if len({packet.task_id for packet in packets}) != len(packets):
        raise ValueError("Plan task identifiers must be unique")
    if plan.total_operations != len(packets):
        raise ValueError("Plan operation count is inconsistent")
    errors = validate_migration_plan(plan, config, conn)
    if errors:
        raise ValueError("Invalid migration plan: " + "; ".join(errors))
    write_migration_plan(conn, plan)
    return plan
