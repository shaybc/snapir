"""Retain exact oversized application requests for local diagnostic inspection."""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import logging
from pathlib import Path

_active_run = ContextVar('oversized_request_run', default=None)


@contextmanager
def capture_for_run(directory):
    """Bind request captures to one run, restoring the previous binding on exit."""
    token = _active_run.set(Path(directory))
    try:
        yield
    finally:
        _active_run.reset(token)


def save_oversized_request(encoded, instruction, report):
    """Save exact intended application text, never provider settings or external files."""
    directory = _active_run.get()
    if directory is None or report['decision'] != 'too_large':
        return
    identity = hashlib.sha256(json.dumps([encoded, instruction, report['stage']],
        ensure_ascii=True).encode('utf-8')).hexdigest()
    folder = directory / 'reports/oversized_model_requests' / identity
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'request.json').write_bytes(encoded.encode('utf-8', errors='surrogatepass'))
        (folder / 'instructions.txt').write_bytes(instruction.encode('utf-8', errors='surrogatepass'))
        metadata = dict(report, capture_id=identity, delivery_status='not_sent_budget_check',
                        scope='Exact application payload and instructions at the named budget-check stage; excludes provider transport settings')
        (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        logging.getLogger(__name__).warning('Saved oversized request materials: %s', folder)
    except OSError:
        logging.getLogger(__name__).warning('Unable to save oversized request materials for this run', exc_info=True)
