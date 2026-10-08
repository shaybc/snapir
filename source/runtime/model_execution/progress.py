"""Report model progress and redacted provider diagnostics without changing requests."""

import asyncio
import logging
from time import monotonic

from runtime.model_execution.component_progress import component_suffix
from runtime.model_execution.error_details import sanitize_diagnostic

logger = logging.getLogger(__name__)


def before_model(callback_context, llm_request):
    """Show the actual ADK request before it is handed to the provider."""
    logger.info("Sending model request; waiting for the provider response.%s", component_suffix())
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Model request: %s", sanitize_diagnostic(
            llm_request.model_dump_json(exclude_none=True)))


def after_model(callback_context, llm_response):
    """Report receipt and expose response content only in diagnostic output."""
    logger.info("Provider response received.%s", component_suffix())
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Model response: %s", sanitize_diagnostic(
            llm_response.model_dump_json(exclude_none=True)))


async def request_headers(request):
    """Log SDK HTTP request metadata with authentication removed."""
    logger.debug("HTTP request: %s %s; headers=%s", request.method,
                 sanitize_diagnostic(str(request.url)),
                 sanitize_diagnostic(str(dict(request.headers))))


async def response_headers(response):
    """Log SDK HTTP response metadata without consuming its body."""
    logger.debug("HTTP response: status=%s; headers=%s", response.status_code,
                 sanitize_diagnostic(str(dict(response.headers))))


async def wait_with_progress(awaitable, timeout):
    """Emit periodic waiting messages while retaining the existing total timeout."""
    started = monotonic()
    task = asyncio.ensure_future(asyncio.wait_for(awaitable, timeout))
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=15)
            if not done:
                logger.info("Still waiting for model execution (%.0f seconds elapsed).%s",
                            monotonic() - started, component_suffix())
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
