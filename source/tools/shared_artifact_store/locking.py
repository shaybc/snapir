"""Coordinate publishers using process-owned locks that release after a crash."""
from contextlib import contextmanager
import os
from pathlib import Path
import time


@contextmanager
def artifact_lock(root, identity, *, timeout=300):
    """Serialize a conversion identity across local processes without stale lock files."""
    from tools.shared_artifact_store.manifests import content_hash
    directory = Path(root) / '.locks'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (content_hash(identity) + '.lock')).open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Another conversion still owns the shared artifact')
                time.sleep(0.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
