"""Concise conversion progress and infrequent wait notices, independent of timeout enforcement."""
import json
import math
from pathlib import Path
import sys
import threading
import time

NOTICE_SECONDS = 120
COMPARISON_PHASES = dict(analysis='indexing source code', boundary='checking input/output mapping',
    inventory='identifying original behavior', mapping='finding generated counterparts',
    compare='comparing behavior', review_difference='reviewing a suspected difference',
    coverage='checking generated-code coverage', interaction='checking related behavior', complete='finishing the review')


def concise(value, limit=400):
    """Keep a potentially multiline diagnostic to one bounded console message."""
    value = ' '.join(str(value).split())
    return value if len(value) <= limit else value[:limit] + '...'


def announce(value):
    """Flush one human-readable line without exposing prompts, source bodies or credentials."""
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    print(str(value).encode(encoding, errors='replace').decode(encoding), flush=True)


def duration(seconds):
    """Display elapsed/limit durations without implying percentage completion."""
    seconds = max(0, int(seconds))
    return str(seconds // 60) + 'm ' + str(seconds % 60) + 's' if seconds >= 60 else str(seconds) + 's'


class WaitProgress:
    """Observe a wait; notifications never count as model content or extend a deadline."""
    def __init__(self, label, timeout, *, inactivity=None, snapshot=None):
        self.label, self.timeout = label, timeout
        self.inactivity, self.snapshot = inactivity, Path(snapshot) if snapshot else None
        self.started = self.last_notice = time.monotonic()
        self.stopped = threading.Event()
        self.thread = None
        self.ai_announced = False
        self.call = None
        self.call_observed = self.started

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()

    def start(self):
        """Watch a blocking operation in a daemon thread, without controlling its lifetime."""
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        """Stop notices immediately when the operation completes or raises."""
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _watch(self):
        while not self.stopped.wait(1):
            self.update()

    def update(self):
        """Report coarse model activity and elapsed time at a bounded frequency."""
        if self.stopped.is_set():
            return
        now = time.monotonic()
        detail = {}
        if self.snapshot:
            try:
                value = json.loads(self.snapshot.read_text(encoding='utf-8'))
                if (isinstance(value, dict) and value.get('schema_version') == 'java-behavior-progress-v1'
                        and isinstance(value.get('phase'), str) and isinstance(value.get('activity'), str)):
                    detail = value
            except (OSError, ValueError):
                pass  # Progress is optional; it never affects acceptance of the final report.
        if self.stopped.is_set():
            return
        call = detail.get('model_call')
        if type(call) is int and call > 0:
            if not self.ai_announced and detail.get('phase') != 'complete':
                announce('Comparison: source analysis complete; reviewing behavior with the model.')
                self.ai_announced = True
            if call != self.call:
                self.call, self.call_observed = call, now
        if now - self.last_notice < NOTICE_SECONDS:
            return
        self.last_notice = now
        text = self.label + ': still active; elapsed ' + duration(now - self.started)
        if self.inactivity:
            text += ', without model content ' + duration(self.inactivity()) + ' (inactivity limit ' + duration(self.timeout) + ')'
        else:
            text += ' of maximum ' + duration(self.timeout)
        if detail.get('phase') in COMPARISON_PHASES:
            text += '; ' + COMPARISON_PHASES[detail['phase']]
        limit = detail.get('model_timeout_seconds')
        if (self.call and detail.get('activity') == 'waiting' and type(limit) in {int, float}
                and math.isfinite(limit) and limit > 0):
            text += ', model call ' + str(self.call) + ': waiting ' + duration(now - self.call_observed)
            text += ' of maximum ' + duration(limit)
        if not self.stopped.is_set():
            announce(text + '.')
