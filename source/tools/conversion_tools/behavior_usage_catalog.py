"""Query global behavior-unit consumers without retaining their XML evidence in memory."""

import hashlib
import json


class DefinitionLookup:
    """Load only definitions requested by the selected unit builder."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id

    def __getitem__(self, identity):
        row = self.conn.execute('SELECT record_json FROM configured_component_definitions WHERE run_id=? AND definition_id=?',
                                (self.run_id, identity)).fetchone()
        if row is None:
            raise KeyError(identity)
        return json.loads(row[0])


class OperationUses:
    """Materialize one original operation's configuration only when comparing a unit."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id

    def __getitem__(self, operation_key):
        return [json.loads(row[0]) for row in self.conn.execute(
            'SELECT record_json FROM configured_component_uses WHERE run_id=? AND operation_key=?', (self.run_id, operation_key))]


class FormatUses:
    """Offer repeatable streaming iteration for global format consumer comparisons."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id

    def __iter__(self):
        return (json.loads(row[0]) for row in self.conn.execute(
            "SELECT record_json FROM configured_component_uses WHERE run_id=? AND component_kind='format'", (self.run_id,)))


class StepCandidates:
    """Index canonical step signatures on disk while preserving global consumer matching."""

    def __init__(self, conn, run_id, canonicalize):
        self.conn, self.run_id = conn, run_id
        conn.execute('CREATE TEMP TABLE IF NOT EXISTS behavior_step_candidates (run_id TEXT, implementation TEXT, signature TEXT, use_id TEXT, PRIMARY KEY(run_id,use_id))')
        conn.execute('DELETE FROM behavior_step_candidates WHERE run_id=?', (run_id,))
        conn.execute('CREATE INDEX IF NOT EXISTS behavior_step_signatures ON behavior_step_candidates(run_id,implementation,signature)')
        for row in conn.execute("SELECT use_id,implementation_id,record_json FROM configured_component_uses WHERE run_id=? AND component_kind='opStep'", (run_id,)):
            signature = hashlib.sha256(canonicalize(json.loads(row[2])['configuration_xml']).encode()).hexdigest()
            conn.execute('INSERT INTO behavior_step_candidates VALUES (?,?,?,?)', (run_id, row[1] or '', signature, row[0]))

    def __getitem__(self, key):
        implementation, xml = key
        signature = hashlib.sha256(xml.encode()).hexdigest()
        return (json.loads(row[0]) for row in self.conn.execute('''SELECT u.record_json FROM behavior_step_candidates c
            JOIN configured_component_uses u ON u.run_id=c.run_id AND u.use_id=c.use_id
            WHERE c.run_id=? AND c.implementation=? AND c.signature=?''', (self.run_id, implementation or '', signature)))


class OperationFormats:
    """Read the relevant operation's format metadata instead of a workspace-wide dictionary."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id

    def get(self, key, default=None):
        channel, name = key
        result = default
        for row in self.conn.execute("SELECT metadata_json FROM source_artifacts WHERE run_id=? AND kind='operation' AND logical_id=?", (self.run_id, name)):
            metadata = json.loads(row[0])
            if metadata.get('channel') == channel:
                result = metadata.get('ref_formats', {})
        return result
