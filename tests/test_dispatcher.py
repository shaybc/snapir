from __future__ import annotations

import time
from pathlib import Path

from snapir.dispatcher import Dispatcher, DispatcherPolicy, Operation


def test_dispatcher_batches_by_dependency_readiness_and_max_parallel() -> None:
    starts: list[tuple[str, float]] = []
    finishes: list[tuple[str, float]] = []

    def make_op(op_id: str, delay: float, deps: tuple[str, ...] = ()) -> Operation:
        def _run(_ctx):
            starts.append((op_id, time.monotonic()))
            time.sleep(delay)
            finishes.append((op_id, time.monotonic()))
            return op_id

        return Operation(id=op_id, dependencies=deps, run=_run)

    dispatcher = Dispatcher(DispatcherPolicy(max_parallel_operations=2, llm_concurrency=1, llm_timeout_seconds=1.0))
    results = dispatcher.dispatch(
        [
            make_op("root_a", 0.1),
            make_op("root_b", 0.1),
            make_op("dep", 0.05, deps=("root_a", "root_b")),
        ]
    )

    assert results["root_a"].status == "success"
    assert results["root_b"].status == "success"
    assert results["dep"].status == "success"

    start_map = dict(starts)
    finish_map = dict(finishes)
    assert start_map["dep"] >= finish_map["root_a"]
    assert start_map["dep"] >= finish_map["root_b"]


def test_dispatcher_respects_llm_queue_and_timeout() -> None:
    def slow_llm(_ctx):
        time.sleep(0.15)
        return "slow"

    def fast_llm(_ctx):
        return "fast"

    dispatcher = Dispatcher(DispatcherPolicy(max_parallel_operations=2, llm_concurrency=1, llm_timeout_seconds=0.05))
    results = dispatcher.dispatch(
        [
            Operation(id="slow", run=slow_llm, requires_llm=True),
            Operation(id="fast", run=fast_llm, requires_llm=True),
        ]
    )

    statuses = {results["slow"].status, results["fast"].status}
    assert "timeout" in statuses
    assert "success" in statuses


def test_dispatcher_serializes_shared_state_writes() -> None:
    def writer(ctx, index: int):
        def _inner(_):
            for _ in range(10):
                ctx.write_shared(lambda state: state.__setitem__("count", state.get("count", 0) + 1))
            return index

        return _inner

    dispatcher = Dispatcher(DispatcherPolicy(max_parallel_operations=4, llm_concurrency=1, llm_timeout_seconds=1.0))
    operations = [Operation(id=f"op_{i}", run=lambda ctx, i=i: writer(ctx, i)(ctx)) for i in range(8)]

    state: dict[str, int] = {}
    results = dispatcher.dispatch(operations, initial_state=state)

    assert all(result.status == "success" for result in results.values())
    assert state["count"] == 80
