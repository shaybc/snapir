from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from threading import Lock, Semaphore
from time import monotonic
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class Operation:
    """A unit of work with dependency and runtime requirements."""

    id: str
    run: Callable[["OperationContext"], Any]
    dependencies: tuple[str, ...] = ()
    requires_llm: bool = False
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class DispatcherPolicy:
    max_parallel_operations: int
    llm_concurrency: int
    llm_timeout_seconds: float


@dataclass
class OperationResult:
    operation_id: str
    status: str
    value: Any = None
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class OperationContext:
    """Runtime services exposed to operations."""

    shared_state: dict[str, Any]
    _write_lock: Lock

    def write_shared(self, writer: Callable[[dict[str, Any]], None]) -> None:
        """Serialize writes to shared state/artifacts."""
        with self._write_lock:
            writer(self.shared_state)


@dataclass
class Dispatcher:
    policy: DispatcherPolicy
    _write_lock: Lock = field(default_factory=Lock)

    def dispatch(self, operations: Iterable[Operation], initial_state: dict[str, Any] | None = None) -> dict[str, OperationResult]:
        ops = {op.id: op for op in operations}
        if not ops:
            return {}

        missing = {
            dep
            for op in ops.values()
            for dep in op.dependencies
            if dep not in ops
        }
        if missing:
            raise ValueError(f"Unknown dependencies: {sorted(missing)}")

        context = OperationContext(shared_state=initial_state if initial_state is not None else {}, _write_lock=self._write_lock)
        completed: dict[str, OperationResult] = {}
        running: dict[Future[OperationResult], Operation] = {}
        llm_sem = Semaphore(max(1, self.policy.llm_concurrency))

        with ThreadPoolExecutor(max_workers=max(1, self.policy.max_parallel_operations)) as pool:
            while len(completed) < len(ops):
                ready = [
                    op
                    for op in ops.values()
                    if op.id not in completed
                    and op.id not in {item.id for item in running.values()}
                    and all(dep in completed and completed[dep].status == "success" for dep in op.dependencies)
                ]

                available_slots = self.policy.max_parallel_operations - len(running)
                for op in ready[:max(0, available_slots)]:
                    running[pool.submit(self._run_operation, op, context, llm_sem)] = op

                if not running:
                    unresolved = [
                        op.id
                        for op in ops.values()
                        if op.id not in completed
                    ]
                    raise RuntimeError(f"Dispatch deadlock; unresolved operations: {unresolved}")

                done, _ = wait(running.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    result = future.result()
                    completed[result.operation_id] = result
                    del running[future]

        return completed

    def _run_operation(self, operation: Operation, context: OperationContext, llm_sem: Semaphore) -> OperationResult:
        start = monotonic()
        timeout = operation.timeout_seconds

        if operation.requires_llm:
            queue_timeout = timeout if timeout is not None else self.policy.llm_timeout_seconds
            acquired = llm_sem.acquire(timeout=queue_timeout)
            if not acquired:
                return OperationResult(
                    operation_id=operation.id,
                    status="timeout",
                    error="timed_out_waiting_for_llm_slot",
                    duration_seconds=monotonic() - start,
                )

        try:
            call_timeout = timeout
            if call_timeout is None:
                value = operation.run(context)
                return OperationResult(operation_id=operation.id, status="success", value=value, duration_seconds=monotonic() - start)

            with ThreadPoolExecutor(max_workers=1) as operation_pool:
                future = operation_pool.submit(operation.run, context)
                try:
                    value = future.result(timeout=call_timeout)
                    return OperationResult(operation_id=operation.id, status="success", value=value, duration_seconds=monotonic() - start)
                except TimeoutError:
                    return OperationResult(
                        operation_id=operation.id,
                        status="timeout",
                        error="operation_execution_timeout",
                        duration_seconds=monotonic() - start,
                    )
                except Exception as exc:  # noqa: BLE001
                    return OperationResult(
                        operation_id=operation.id,
                        status="failed",
                        error=str(exc),
                        duration_seconds=monotonic() - start,
                    )
        except Exception as exc:  # noqa: BLE001
            return OperationResult(operation_id=operation.id, status="failed", error=str(exc), duration_seconds=monotonic() - start)
        finally:
            if operation.requires_llm:
                llm_sem.release()
