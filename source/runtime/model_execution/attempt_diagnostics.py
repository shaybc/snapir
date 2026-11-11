"""Record application materials and correlated model events without changing execution."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
import uuid

from runtime.model_execution.error_details import sanitize_diagnostic

_directory = ContextVar('ai_diagnostic_directory', default=None)
_attempt = ContextVar('ai_diagnostic_attempt', default=None)
_delivery = ContextVar('ai_diagnostic_delivery', default=None)
_lock = RLock()


@contextmanager
def capture_attempts_for_run(directory):
    """Bind append-only evidence to the active run without creating migration state."""
    token = _directory.set(Path(directory))
    try:
        yield
    finally:
        _directory.reset(token)


@contextmanager
def attempt_scope(category, identity, fingerprint='', attempt=None, label=''):
    """Carry one logical generation attempt through nested staged/transport wrappers."""
    trace = dict(trace_id=uuid.uuid4().hex, category=category, identity=identity,
                 fingerprint=fingerprint, attempt=attempt, label=label)
    token = _attempt.set(trace)
    try:
        yield trace
    finally:
        _attempt.reset(token)


@contextmanager
def model_scope(payload, instruction, label=''):
    """Reuse an existing generation scope, or identify an otherwise standalone call."""
    if _attempt.get() is not None:
        emit('application_request', request=payload, instructions=instruction)
        yield _attempt.get()
    else:
        try:
            value = json.loads(payload)
            identity = value.get('group_id') or value.get('unit_id') or value.get('operation_identity') or label or 'unidentified'
        except (ValueError, AttributeError, TypeError):
            identity = label or 'unidentified'
        with attempt_scope('model_call', identity, label=label) as trace:
            emit('application_request', request=payload, instructions=instruction)
            yield trace


@contextmanager
def delivery_scope(number):
    """Identify each bounded transport attempt independently of conversion corrections."""
    token = _delivery.set(dict(delivery_id=uuid.uuid4().hex, delivery_attempt=number))
    try:
        emit('dispatch_attempted')
        yield
    finally:
        _delivery.reset(token)


def _blob(folder, text):
    data = text.encode('utf-8', errors='surrogatepass')
    identity = hashlib.sha256(data).hexdigest()
    destination = folder / 'blobs' / (identity + '.txt')
    if destination.is_symlink() or not destination.resolve().is_relative_to(folder.resolve()):
        raise ValueError('AI diagnostic material must remain inside its capture folder')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = None
        try:
            with NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return identity


def emit(event, *, trace=None, request=None, instructions=None, response=None, **details):
    """Best-effort capture; never change retry decisions or propagate diagnostic IO errors."""
    directory = _directory.get()
    if directory is None:
        return
    folder = directory / 'reports/model_attempts'
    record = dict(_attempt.get() or {}, **(_delivery.get() or {}))
    if trace is not None:
        record.update(trace)
    record.update(event=event, timestamp=datetime.now(timezone.utc).isoformat())
    record.update(details)
    if record.get('error') is not None:
        error = record['error']
        if isinstance(error, BaseException):
            record['error_type'] = type(error).__name__
        record['error'] = sanitize_diagnostic(str(error).strip() or record.get('error_type') or 'Unspecified error')
    try:
        with _lock:
            if folder.is_symlink() or not folder.resolve().is_relative_to(directory.resolve()):
                raise ValueError('AI diagnostic capture must remain inside its run')
            folder.mkdir(parents=True, exist_ok=True)
            for name, text in (('request', request), ('instructions', instructions), ('response', response), ('error', record.get('error'))):
                if text is not None:
                    record[name + '_blob'] = _blob(folder, text)
            data = (json.dumps(record, ensure_ascii=True) + '\n').encode('utf-8')
            journal = folder / 'events.jsonl'
            if journal.is_symlink():
                raise ValueError('AI diagnostic journal must not be a symbolic link')
            descriptor = os.open(journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(descriptor, data)
            finally:
                os.close(descriptor)
    except (OSError, ValueError, TypeError):
        logging.getLogger(__name__).warning('Unable to retain AI attempt diagnostic evidence')


def record_budget(request, encoded, instruction, report):
    """Record checks as checks, including intermediate oversized requests never dispatched."""
    identity = request.get('group_id') or request.get('unit_id') or request.get('operation_identity') or report.get('request_id')
    emit('budget_check', request=encoded, instructions=instruction, identity=identity,
         budget_stage=report['stage'], decision=report['decision'],
         characters=report['total']['characters'], character_limit=report['character_limit'])
