"""Optional diagnostic snapshots for CLI callers; JSON result and comparison policy stay independent."""
import json
import os
from pathlib import Path
import tempfile
from contextvars import ContextVar

ENVIRONMENT = 'JAVA_BEHAVIOR_PROGRESS_PATH'
BLOCKED_PATH = ContextVar('behavior_progress_blocked_path', default=None)


def protect_inputs(request):
    """Ignore diagnostic paths inside inspected inputs, preserving the comparator's read-only contract."""
    selected = os.environ.get(ENVIRONMENT)
    BLOCKED_PATH.set(None)
    if not selected:
        return
    try:
        destination = Path(selected).resolve()
    except (OSError, ValueError):
        BLOCKED_PATH.set(selected)
        return
    for side in ('original', 'generated'):
        for role in ('sources', 'dependency_sources', 'jars'):
            for value in request[side].get(role, []):
                root = Path(value).resolve()
                if destination == root or root.is_dir() and destination.is_relative_to(root):
                    BLOCKED_PATH.set(str(destination))
                    return


def update(phase, activity, *, model_call=0, timeout=None):
    """Atomically publish a small status snapshot without persisting code, prompts or credentials."""
    selected = os.environ.get(ENVIRONMENT)
    if not selected:
        return
    temporary = None
    try:
        destination = Path(selected)
        if str(destination.resolve()) == BLOCKED_PATH.get():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                         prefix='.comparison-progress-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(dict(schema_version='java-behavior-progress-v1', phase=phase, activity=activity,
                           model_call=model_call, model_timeout_seconds=timeout), stream)
        temporary.replace(destination)
    except (OSError, ValueError):
        pass  # An unavailable diagnostic destination must not alter the comparison decision.
    finally:
        if temporary and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
