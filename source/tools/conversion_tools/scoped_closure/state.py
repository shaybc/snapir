"""Persist qualified analysis results without marking legacy conversion state ready."""

import json


def initialize(conn):
    """Add closure/context tables keyed by run, consuming context, and source identity."""
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_operation_closures (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, status TEXT NOT NULL,
        closure_json TEXT NOT NULL, PRIMARY KEY(run_id,operation_identity))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS scoped_context_hierarchies (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, context_definition_id TEXT NOT NULL,
        hierarchy_json TEXT NOT NULL, fields_json TEXT NOT NULL,
        PRIMARY KEY(run_id,operation_identity,context_definition_id))''')
    conn.execute('''CREATE INDEX IF NOT EXISTS scoped_source_coordinates ON scoped_source_definitions
        (run_id,json_extract(record_json,'$.source_relative_path'),json_extract(record_json,'$.source_selector'))''')
    conn.execute('''CREATE INDEX IF NOT EXISTS scoped_source_kind ON scoped_source_definitions
        (run_id,kind,logical_id)''')


def save_closures(conn, closures):
    """Store one completed dependency analysis atomically, leaving generation disabled."""
    conn.execute('SAVEPOINT scoped_closure_analysis')
    try:
        initialize(conn)
        for closure in closures:
            conn.execute('INSERT OR REPLACE INTO scoped_operation_closures VALUES (?,?,?,?)',
                         (closure.run_id, closure.operation_identity, closure.status, closure.model_dump_json()))
            # Rebuilding a changed root must not retain a hierarchy that is no longer selected.
            conn.execute('DELETE FROM scoped_context_hierarchies WHERE run_id=? AND operation_identity=?',
                         (closure.run_id, closure.operation_identity))
            if closure.context_chain:
                conn.execute('INSERT INTO scoped_context_hierarchies VALUES (?,?,?,?,?)',
                             (closure.run_id, closure.operation_identity, closure.context_chain[0]['definition_id'],
                              json.dumps(closure.context_chain, sort_keys=True),
                              json.dumps(closure.context_fields, sort_keys=True)))
        conn.execute('RELEASE SAVEPOINT scoped_closure_analysis')
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT scoped_closure_analysis')
        conn.execute('RELEASE SAVEPOINT scoped_closure_analysis')
        raise
