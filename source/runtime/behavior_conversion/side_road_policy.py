"""Limit temporary architecture relaxation to isolated, verified baseline conversion."""
from contextlib import contextmanager
from contextvars import ContextVar

_stage = ContextVar('side_road_stage', default=None)


class ForbiddenFrameworkDependency(ValueError):
    """A generated source retained a prohibited original runtime dependency."""


def baseline_stage():
    """Return whether only the temporary architecture restriction may be relaxed."""
    return _stage.get() == 'baseline'


@contextmanager
def side_road_stage(stage):
    """Restore normal checks after a baseline or simplification call, including failure."""
    token = _stage.set(stage)
    try:
        yield
    finally:
        _stage.reset(token)
