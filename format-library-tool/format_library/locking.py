"""Refuse overlapping mutations rather than lose approvals or component status updates."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def exclusive(path):
    """Hold a tool-owned lock until completion; a crashed-process lock needs explicit removal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError('Another operation holds ' + str(path) +
            '. If its process crashed, verify it is stopped before removing this lock.') from error
    try:
        os.write(descriptor, str(os.getpid()).encode('ascii'))
        yield
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)
