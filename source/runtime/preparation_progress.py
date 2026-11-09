"""Report long preparation work without claiming completions from heartbeat messages."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging
from threading import Event, Thread, Lock
from time import monotonic

_current = ContextVar('qualified_preparation_progress', default=None)


def report_preparation(message):
    """Identify the active preparation task; a new label does not imply completed work."""
    current = _current.get()
    if current is not None:
        with current['lock']:
            current['detail'] = str(message)
    logging.getLogger(__name__).info('%s', message)


@contextmanager
def preparation_progress(label, *, interval_seconds=10):
    """Keep verification and preparation visible until they complete or fail."""
    logger = logging.getLogger(__name__)
    state = dict(detail=label, lock=Lock())
    token = _current.set(state)
    stopped, started = Event(), monotonic()
    def heartbeat():
        while not stopped.wait(interval_seconds):
            with state['lock']:
                detail = state['detail']
            logger.info('%s still running: %.0f seconds elapsed; current=%s', label, monotonic() - started, detail)
    worker = Thread(target=heartbeat, name='preparation-progress', daemon=True)
    logger.info('%s started.', label)
    worker.start()
    outcome = 'interrupted'
    try:
        yield
        outcome = 'completed'
    finally:
        stopped.set()
        worker.join()
        _current.reset(token)
        logger.info('%s %s after %.1f seconds.', label, outcome, monotonic() - started)
