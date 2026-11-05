"""Report elapsed intake work while synchronous inventory processing is busy."""

from contextlib import contextmanager
import logging
from threading import Event, Thread
from time import monotonic


@contextmanager
def component_inventory_progress(source_count, *, interval_seconds=10):
    """Log periodic liveness and stop reporting on success, failure, or cancellation.

    The source count is the inventory input size, not a completed-file counter.
    """
    logger = logging.getLogger(__name__)
    started = monotonic()
    stopped = Event()

    def report():
        while not stopped.wait(interval_seconds):
            logger.info("Component inventory still running: %.0f seconds elapsed; %s indexed Java source files in scope.",
                        monotonic() - started, source_count)

    worker = Thread(target=report, name="component-inventory-progress", daemon=True)
    worker.start()
    outcome = "interrupted"
    try:
        yield
        outcome = "completed"
    finally:
        stopped.set()
        worker.join()
        logger.info("Component inventory %s after %.1f seconds.", outcome, monotonic() - started)
