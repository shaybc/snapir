"""Additive storage for schema-three execution bindings and intake evidence."""

SCOPED_CONTEXT_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS scoped_operation_contexts (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, channel TEXT NOT NULL,
        operation_id TEXT NOT NULL, definition_id TEXT NOT NULL, note_path TEXT NOT NULL,
        selected INTEGER NOT NULL, record_json TEXT NOT NULL,
        PRIMARY KEY(run_id, operation_identity), UNIQUE(run_id, channel, operation_id))''',
    '''CREATE TABLE IF NOT EXISTS scoped_context_bindings (
        run_id TEXT NOT NULL, operation_identity TEXT NOT NULL, binding_kind TEXT NOT NULL,
        binding_key TEXT NOT NULL, definition_id TEXT NOT NULL, note_path TEXT NOT NULL,
        PRIMARY KEY(run_id, operation_identity, binding_kind, binding_key))''',
    '''CREATE TABLE IF NOT EXISTS scoped_channel_evidence (
        run_id TEXT NOT NULL, channel TEXT NOT NULL, note_path TEXT NOT NULL,
        note_hash TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(run_id, channel))''',
    '''CREATE TABLE IF NOT EXISTS scoped_intake_evidence (
        run_id TEXT PRIMARY KEY, identity_version INTEGER NOT NULL,
        evidence_hash TEXT NOT NULL, record_json TEXT NOT NULL)''',
    '''CREATE INDEX IF NOT EXISTS scoped_usage_note ON scoped_entity_usages(run_id, note_path)''',
)
