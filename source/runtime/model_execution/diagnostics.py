"""Retain redacted runtime failure evidence in the selected run workspace."""

import logging
import sys
from contextlib import contextmanager

from runtime.model_execution.error_details import SafeDiagnosticFormatter


@contextmanager
def run_model_diagnostics(directory):
    """Attach a run file sink temporarily without changing logger levels or retries."""
    try:
        path = directory / "logs" / "model_execution.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    except OSError:
        logging.getLogger(__name__).warning("Unable to save model diagnostics in the run logs directory.")
        yield
        return
    handler.setFormatter(SafeDiagnosticFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    loggers = [logging.getLogger(name) for name in ("cli", "runtime", "agents", "tools", "google_adk")]
    levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        if sys.exc_info()[0] is not None:
            logging.getLogger("runtime").error("Migration action failed", exc_info=sys.exc_info())
        for logger, level in zip(loggers, levels):
            logger.removeHandler(handler)
            logger.setLevel(level)
        handler.close()
