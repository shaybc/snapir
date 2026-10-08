"""Prepare persisted assembly plans from READY closures."""

from tools.conversion_tools.context_plan_builder_tool import build_context_plan
from tools.conversion_tools.routing_plan_builder_tool import build_routing_plan
from tools.conversion_tools.serialization_plan_builder_tool import build_serialization_plan
from tools.state_store_tools.operation_closures import get_operation_closure


def prepare_assembly_plans(conn, config, packet):
    """Build routing, context, and serialization plans for one channel-qualified operation."""
    closure = get_operation_closure(conn, packet.operation_id, packet.channel, config.run_id)
    if closure is None or closure["status"] != "READY":
        raise ValueError("Assembly requires a READY operation closure")
    return (
        build_routing_plan(conn, packet.operation_id, packet.channel, config.run_id),
        build_context_plan(conn, packet.operation_id, packet.channel, config.run_id),
        build_serialization_plan(conn, packet.operation_id, packet.channel, config.run_id, config.vault_root),
    )
