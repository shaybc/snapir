"""Runtime console diagnostics for migration CLI invocations."""

import logging
from contextlib import contextmanager


class _ConsoleFormatter(logging.Formatter):
    """Keep exception details on records while hiding console traces by default."""

    def __init__(self, verbose: bool):
        super().__init__("%(levelname)s: %(message)s")
        self.verbose = verbose

    def format(self, record: logging.LogRecord) -> str:
        if self.verbose:
            return super().format(record)
        # Format a copy so file handlers retain the original exception evidence.
        concise = logging.makeLogRecord(record.__dict__.copy())
        concise.exc_info = None
        concise.exc_text = None
        concise.stack_info = None
        return super().format(concise)


@contextmanager
def console_diagnostics(verbose: bool):
    """Configure app and ADK console logs for one invocation, then restore them."""
    saved = []
    handler = logging.StreamHandler()
    handler.setFormatter(_ConsoleFormatter(verbose))
    for name in ("cli", "runtime", "agents", "tools", "google_adk"):
        logger = logging.getLogger(name)
        saved.append((logger, logger.level, logger.propagate, logger.handlers[:]))
        file_handlers = [item for item in logger.handlers if isinstance(item, logging.FileHandler)]
        # Preserve file sinks inherited from the root while replacing console output.
        if logger.propagate:
            for item in logging.getLogger().handlers:
                if isinstance(item, logging.FileHandler) and item not in file_handlers:
                    file_handlers.append(item)
        logger.handlers = file_handlers
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if verbose else (
            logging.WARNING if name == "google_adk" else logging.INFO))
        logger.propagate = False
    try:
        yield
    finally:
        for logger, level, propagate, handlers in saved:
            logger.handlers = handlers
            logger.setLevel(level)
            logger.propagate = propagate
        handler.close()
