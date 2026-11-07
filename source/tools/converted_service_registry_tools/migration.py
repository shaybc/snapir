"""Import old shared API records without deleting or rewriting their original registry."""
import logging
from pathlib import Path
import sqlite3


def migrate_legacy_services(conn):
    """Keep legacy callable contracts available; missing local packages do not erase remote APIs."""
    from runtime.project_paths import project_root
    from tools.converted_service_registry_tools.registry import publish_service
    for path in (project_root() / 'work/service_registry').glob('*/services.db'):
        try:
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as legacy:
                rows = legacy.execute('SELECT contract_json,published_at FROM converted_operation_services ORDER BY published_at').fetchall()
            for row in rows:
                import json
                record = json.loads(row[0])
                if not conn.execute('SELECT 1 FROM converted_operation_services WHERE application_id=? AND channel=? AND operation_id=? AND api_revision=?',
                    (record['application_id'], record['channel'], record['operation_id'], record['api_revision'])).fetchone():
                    publish_service(conn, record)
                    with conn:
                        conn.execute('UPDATE converted_operation_services SET published_at=? WHERE application_id=? AND channel=? AND operation_id=? AND api_revision=?',
                            (row[1], record['application_id'], record['channel'], record['operation_id'], record['api_revision']))
        except (OSError, sqlite3.DatabaseError, ValueError, KeyError) as error:
            logging.getLogger(__name__).warning('Legacy service registry could not be imported: %s: %s', path, error)
