"""Report elapsed intake work while synchronous inventory processing is busy."""

from contextlib import contextmanager
import logging
from threading import Event, Thread
from time import monotonic
from runtime.inventory_work import InventoryWork, active_inventory_work


@contextmanager
def component_inventory_progress(source_count, *, interval_seconds=10, log_directory=None):
    """Log periodic liveness and stop reporting on success, failure, or cancellation.

    The source count is the inventory input size, not a completed-file counter.
    """
    logger = logging.getLogger(__name__)
    started = monotonic()
    stopped = Event()
    work = InventoryWork(log_directory)
    token = active_inventory_work.set(work)
    file_handler = None
    if log_directory is not None:
        from pathlib import Path
        Path(log_directory).mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(Path(log_directory) / 'intake.log', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        for name in ('runtime', 'tools', 'agents'):
            logging.getLogger(name).addHandler(file_handler)

    def report():
        while not stopped.wait(interval_seconds):
            snapshot = work.snapshot()
            logger.info("Component inventory still running: %.0f seconds elapsed; workspace index=%s Java files; phase=%s; completed=%s/%s; last completed work %.0fs ago; %s",
                        monotonic() - started, source_count, snapshot['phase'], snapshot['completed'],
                        snapshot['total'] if snapshot['total'] is not None else '?', snapshot['idle_seconds'], snapshot['detail'])
            work.persist()

    worker = Thread(target=report, name="component-inventory-progress", daemon=True)
    worker.start()
    outcome = "interrupted"
    try:
        work.persist()
        yield work
        outcome = "completed"
    finally:
        stopped.set()
        worker.join()
        active_inventory_work.reset(token)
        logger.info("Component inventory %s after %.1f seconds.", outcome, monotonic() - started)
        work.status = outcome
        try:
            work.persist()
        finally:
            if file_handler is not None:
                for name in ('runtime', 'tools', 'agents'):
                    logging.getLogger(name).removeHandler(file_handler)
                file_handler.close()
