"""Provide nested state writes without committing a caller's surrounding transaction."""
from contextlib import contextmanager
from uuid import uuid4


@contextmanager
def savepoint(conn):
    """Commit this write only when it owns the outer transaction; roll back on errors."""
    name = 'state_' + uuid4().hex
    conn.execute('SAVEPOINT ' + name)
    try:
        yield
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT ' + name)
        conn.execute('RELEASE SAVEPOINT ' + name)
        raise
    conn.execute('RELEASE SAVEPOINT ' + name)
