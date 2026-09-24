from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from constants import INTER_BATCH_DELAY_SECS
from models.common_models import RunConfig
from models.migration_models import MigrationBatch, MigrationPlan, MigrationTaskPacket
from tools.routing_tools.batch_progress_tracker import update_progress


@dataclass(frozen=True)
class BatchResult:
    """Dispatch result for one migration batch."""

    batch_id: str
    success_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0


@dataclass(frozen=True)
class RunResult:
    """Dispatch result for a full migration plan."""

    run_id: str
    batch_results: list[BatchResult] = field(default_factory=list)
    common_lib_rebuilds: int = 0


PhaseHandler = Callable[[sqlite3.Connection, MigrationTaskPacket, RunConfig], str | tuple[str, str | None]]


def dispatch_batch(
    conn: sqlite3.Connection,
    batch: MigrationBatch,
    run_config: RunConfig,
    on_operation_complete: Callable[[str], None],
    on_operation_failed: Callable[[str, str | None], None],
    phase_handlers: dict[str, PhaseHandler] | None = None,
) -> BatchResult:
    """Process all operations in a batch through phases 2-6."""
    handlers = phase_handlers or {}
    states: dict[str, tuple[str, str | None]] = {
        packet.operation_id: ("pending", None) for packet in batch.task_packets
    }

    for packet in batch.task_packets:
        states[packet.operation_id] = _run_phase(conn, packet, run_config, handlers.get("closure"))

    active = [packet for packet in batch.task_packets if states[packet.operation_id][0] != "blocked"]
    states.update(_run_parallel(conn, active, run_config, handlers.get("conversion"), run_config.max_parallel_conversion_workers))

    for packet in batch.task_packets:
        if states[packet.operation_id][0] != "blocked":
            states[packet.operation_id] = _run_phase(conn, packet, run_config, handlers.get("assembly"))

    active = [packet for packet in batch.task_packets if states[packet.operation_id][0] != "blocked"]
    states.update(_run_parallel(conn, active, run_config, handlers.get("generation"), run_config.max_parallel_build_tasks))

    active = [packet for packet in batch.task_packets if states[packet.operation_id][0] != "blocked"]
    states.update(_run_parallel(conn, active, run_config, handlers.get("validation"), run_config.max_parallel_build_tasks))

    success_count = failed_count = blocked_count = 0
    for packet in batch.task_packets:
        status, reason = states[packet.operation_id]
        update_progress(conn, batch.run_id, batch.batch_id, packet.operation_id, status)
        if status in {"completed", "validated"}:
            success_count += 1
            on_operation_complete(packet.operation_id)
        elif status == "blocked":
            blocked_count += 1
            on_operation_failed(packet.operation_id, reason)
        else:
            failed_count += 1
            on_operation_failed(packet.operation_id, reason)
    return BatchResult(batch.batch_id, success_count, failed_count, blocked_count)


def dispatch_all_batches(
    conn: sqlite3.Connection,
    plan: MigrationPlan,
    run_config: RunConfig,
    phase_handlers: dict[str, PhaseHandler] | None = None,
    common_lib_rebuilder: Callable[[sqlite3.Connection, str], bool] | None = None,
) -> RunResult:
    """Dispatch all migration batches in plan order."""
    results = []
    rebuilds = 0
    for index, batch in enumerate(plan.batches):
        result = dispatch_batch(
            conn,
            batch,
            run_config,
            on_operation_complete=lambda operation_id: None,
            on_operation_failed=lambda operation_id, reason: None,
            phase_handlers=phase_handlers,
        )
        results.append(result)
        if _has_shared_promotions(conn, plan.run_id) and common_lib_rebuilder:
            if common_lib_rebuilder(conn, plan.run_id):
                rebuilds += 1
        if index < len(plan.batches) - 1:
            time.sleep(INTER_BATCH_DELAY_SECS)
    return RunResult(run_id=plan.run_id, batch_results=results, common_lib_rebuilds=rebuilds)


def _run_parallel(
    conn: sqlite3.Connection,
    packets: list[MigrationTaskPacket],
    run_config: RunConfig,
    handler: PhaseHandler | None,
    max_workers: int,
) -> dict[str, tuple[str, str | None]]:
    if not packets:
        return {}
    workers = max(1, max_workers)
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run_phase, conn, packet, run_config, handler): packet.operation_id
            for packet in packets
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


def _run_phase(
    conn: sqlite3.Connection,
    packet: MigrationTaskPacket,
    run_config: RunConfig,
    handler: PhaseHandler | None,
) -> tuple[str, str | None]:
    if handler is None:
        return "completed", None
    result = handler(conn, packet, run_config)
    if isinstance(result, tuple):
        return result
    return result, None


def _has_shared_promotions(conn: sqlite3.Connection, run_id: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM component_registry
        WHERE run_id IN (?, 'global') AND used_by_validated_operations > 0
        """,
        (run_id,),
    ).fetchone()
    return bool(row and row["count"])
