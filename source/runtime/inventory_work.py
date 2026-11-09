"""Persist actual inventory work counters and capture diagnostic stacks during inactivity."""

import faulthandler
import json
import logging
import os
from pathlib import Path
import tempfile
from threading import RLock
from time import monotonic
from contextvars import ContextVar

active_inventory_work = ContextVar('active_inventory_work', default=None)


class InventoryWork:
    """Track meaningful completions separately from a periodic console heartbeat."""

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else None
        self.lock = RLock()
        self.started = self.last_work = self.last_report = monotonic()
        self.last_stack = self.started
        self.phase = 'Preparing inventory'
        self.status = 'running'
        self.completed, self.total, self.detail = 0, None, ''

    def stage(self, name, total=None):
        """Begin a named phase, making expensive phase boundaries visible immediately."""
        with self.lock:
            self.phase, self.total, self.completed, self.detail = name, total, 0, ''
            self.last_work = monotonic()
            logging.getLogger(__name__).info('Inventory phase: %s; total=%s.', name, total if total is not None else 'discovering')

    def advance(self, count=1, detail=''):
        """Record real completed work; heartbeats never call this method."""
        with self.lock:
            self.completed += count
            self.detail = detail
            self.last_work = monotonic()
            if self.last_work - self.last_report >= 5 or self.completed == self.total:
                logging.getLogger(__name__).info('Inventory progress: %s; %s/%s; %s', self.phase,
                    self.completed, self.total if self.total is not None else '?', detail)
                self.last_report = self.last_work

    def current(self, detail):
        """Identify active work without pretending that work has completed."""
        with self.lock:
            self.detail = detail

    def snapshot(self):
        """Return phase/count/idle evidence suitable for console and a small JSON file."""
        with self.lock:
            now = monotonic()
            return dict(status=self.status, phase=self.phase, completed=self.completed, total=self.total, detail=self.detail,
                        elapsed_seconds=round(now-self.started, 1), idle_seconds=round(now-self.last_work, 1))

    def persist(self):
        """Write an atomic snapshot and a periodic stack trace after 120 seconds without work."""
        if self.directory is None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        snapshot = self.snapshot()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.directory, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(snapshot, stream)
            os.replace(temporary, self.directory / 'intake-progress.json')
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        now = monotonic()
        if snapshot['idle_seconds'] >= 120 and now-self.last_stack >= 120:
            with (self.directory / 'intake-stacks.log').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(snapshot) + '\n')
                stream.flush()
                faulthandler.dump_traceback(file=stream, all_threads=True)
            self.last_stack = now
            logging.getLogger(__name__).warning('No completed inventory work for %.0f seconds; diagnostic stacks saved to intake-stacks.log.', snapshot['idle_seconds'])
