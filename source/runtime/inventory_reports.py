"""Write inventory reports incrementally without building whole JSON strings."""

from collections.abc import Mapping, Iterable
from dataclasses import fields, is_dataclass
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import Event, Thread
from time import monotonic


def write_json_report(path, value):
    """Atomically stream ordinary report schemas, holding only one record at a time."""
    path = Path(path)
    from runtime.inventory_work import active_inventory_work
    work = active_inventory_work.get()
    if work is not None:
        work.stage('Writing inventory report: ' + path.name)
        work.current(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    logger = logging.getLogger(__name__)
    started, stopped = monotonic(), Event()

    def heartbeat():
        while not stopped.wait(10):
            logger.info('Writing %s incrementally; %.0f seconds elapsed.', path.name, monotonic() - started)

    worker = Thread(target=heartbeat, name='inventory-report-progress', daemon=True)
    worker.start()
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            _write(stream, value)
            stream.write('\n')
        os.replace(temporary, path)
        if work is not None:
            work.advance(detail='Report saved: ' + path.name)
        logger.info('Wrote %s: %s bytes in %.1f seconds.', path.name, path.stat().st_size, monotonic() - started)
    finally:
        stopped.set()
        worker.join()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write(stream, value):
    if hasattr(type(value), 'model_fields'):
        value = {name: getattr(value, name) for name in type(value).model_fields}
    elif is_dataclass(value):
        value = {item.name: getattr(value, item.name) for item in fields(value)}
    elif hasattr(value, 'model_dump_json'):
        value = json.loads(value.model_dump_json())
    if isinstance(value, Mapping):
        stream.write('{')
        for index, (key, item) in enumerate(value.items()):
            if index:
                stream.write(',')
            stream.write(json.dumps(key) + ':')
            _write(stream, item)
        stream.write('}')
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        stream.write('[')
        for index, item in enumerate(value):
            if index:
                stream.write(',')
            _write(stream, item)
        stream.write(']')
    else:
        stream.write(json.dumps(value, ensure_ascii=True))
