"""Estimate remaining note-validation time from recent observed batch throughput."""

from collections import deque
from time import monotonic


def format_duration(seconds):
    """Format nonnegative seconds as a compact duration for console estimates."""
    seconds = max(0, round(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds}s"


class ComposerMapEstimate:
    """Track five recent batches without treating finalization as note processing."""

    def __init__(self, total, *, started=None):
        self.total = total
        self.started = monotonic() if started is None else started
        self.previous_time = self.started
        self.previous_count = 0
        self.batches = deque(maxlen=5)

    def update(self, processed, *, now=None):
        """Return observed counts and an approximate ETA once 250 notes are checked."""
        now = monotonic() if now is None else now
        elapsed = max(0, now - self.started)
        if processed > self.total:
            return f"Validated {processed:,} notes; manifest count changed; remaining time unavailable"
        percent = 100 * processed / self.total if self.total else 100
        prefix = f"Validated {processed:,} / {self.total:,} notes ({percent:.0f}%) | Elapsed: {format_duration(elapsed)}"
        if processed == self.total:
            return prefix + " | Finalizing validation"
        if processed < 250:
            return prefix + " | Estimating remaining time after 250 notes"
        if processed > self.previous_count and now > self.previous_time:
            self.batches.append((processed - self.previous_count, now - self.previous_time))
            self.previous_count = processed
            self.previous_time = now
        notes = sum(count for count, _ in self.batches)
        seconds = sum(duration for _, duration in self.batches)
        if not notes:
            return prefix + " | Estimated remaining: unavailable"
        remaining = (self.total - processed) * seconds / notes
        return prefix + f" | Estimated remaining: ~{format_duration(remaining)}"
