"""Limit automatic corrections within one explicit behavior-pipeline Resume."""

from contextvars import ContextVar
from functools import wraps

_resume_attempts = ContextVar("behavior_resume_attempts", default=None)


def with_resume_budget(function):
    """Start a fresh per-task correction budget and discard it when Resume finishes."""
    @wraps(function)
    def resume(*args, **kwargs):
        token = _resume_attempts.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _resume_attempts.reset(token)
    return resume


def attempt_window(run_id, category, identity, fingerprint, previous_attempt, maximum):
    """Return cumulative bounds without resetting persisted diagnostic attempt numbers."""
    budgets = _resume_attempts.get()
    if budgets is None:
        return 0, maximum
    key = (run_id, category, identity, fingerprint)
    start = budgets.setdefault(key, previous_attempt)
    return start, start + maximum
