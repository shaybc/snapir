"""Number and time post-model validation work for one native unit response."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

_progress = ContextVar("native_validation_progress", default=None)
_logger = logging.getLogger(__name__)


def begin_progress(label):
    """Start an isolated numbered sequence; callers must reset the returned token."""
    return _progress.set({"label": label, "started": monotonic(), "number": 0})


def end_progress(token):
    """Restore the previous sequence, including after failed validation."""
    _progress.reset(token)


@contextmanager
def progress_step(description, failed=None):
    """Log start and completion/failure without changing work or exception behavior."""
    state = _progress.get()
    if state is None:
        yield
        return
    started = monotonic()
    def emit(status):
        state["number"] += 1
        _logger.info("%d. %s %s. [%s; step %.1fs; elapsed %.1fs]",
            state["number"], description, status, state["label"],
            monotonic() - started, monotonic() - state["started"])
    emit("started")
    try:
        yield
    except Exception:
        emit("failed")
        raise
    else:
        emit("failed" if failed is not None and failed() else "completed")
