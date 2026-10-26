"""Read qualified imported evidence without projecting it into legacy name tables."""

import json

from models.operation_execution_context import OperationExecutionContext
from models.scoped_entity_reference import ScopedEntityReference
from models.scoped_step_occurrence import ScopedStepOccurrence


class ScopedVaultAccess:
    """Access one ready schema-three import; lookups never fall back to XML defaults."""

    def __init__(self, conn, run_id):
        self.conn, self.run_id = conn, run_id
        table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scoped_vault_runs'").fetchone()
        run = conn.execute('SELECT schema_version FROM scoped_vault_runs WHERE run_id=?', (run_id,)).fetchone() if table else None
        if not run or run[0] != 3:
            raise ValueError('Qualified access requires a ready schema-three inventory import')

    def operation(self, channel, operation_id):
        """Return the exact consuming context or report missing execution evidence."""
        row = self.conn.execute('''SELECT record_json FROM scoped_operation_contexts
            WHERE run_id=? AND channel=? AND operation_id=?''', (self.run_id, channel, operation_id)).fetchone()
        if not row:
            raise ValueError(f'Missing execution context: {channel}/{operation_id}')
        record = json.loads(row[0])
        return OperationExecutionContext(self.run_id, *(record[key] for key in
            ('operation_identity', 'channel', 'operation_id', 'definition_id', 'note')), evidence=record)

    def _context(self, context):
        # Re-read by identity and run so callers cannot inject another run's bindings.
        if context.run_id != self.run_id:
            raise ValueError('Execution context belongs to another imported run')
        row = self.conn.execute('''SELECT record_json FROM scoped_operation_contexts
            WHERE run_id=? AND operation_identity=?''', (self.run_id, context.operation_identity)).fetchone()
        if not row:
            raise ValueError('Execution context does not belong to this imported run')
        record = json.loads(row[0])
        if record['channel'] != context.channel or record['operation_id'] != context.operation_id:
            raise ValueError('Execution context identity disagrees with imported evidence')
        return record

    def _binding(self, context, kind, key):
        # Public entry points validate the context once, not once per selected step.
        row = self.conn.execute('''SELECT u.record_json FROM scoped_context_bindings b
            JOIN scoped_entity_usages u ON u.run_id=b.run_id AND u.note_path=b.note_path
                AND u.definition_id=b.definition_id
            WHERE b.run_id=? AND b.operation_identity=? AND b.binding_kind=? AND b.binding_key=?''',
            (self.run_id, context.operation_identity, kind, key)).fetchone()
        if not row:
            raise ValueError(f'Missing contextual {kind}: {key}')
        record = json.loads(row[0])
        return ScopedEntityReference(*(record[field] for field in
            ('definition_id', 'usage_id', 'kind', 'entity_id', 'note')), evidence=record)

    def resource(self, context, reference):
        """Return an explicitly selected reference, such as formats:Request or contexts:Ctx."""
        self._context(context)
        return self._binding(context, 'reference', reference)

    def steps(self, context):
        """Yield selected occurrences in effective order with canonical source positions."""
        record = self._context(context)
        calls_by_step = {}
        for call in record['calls']:
            calls_by_step.setdefault(call['step_note'], []).append(call)
        for index, note in enumerate(record['step_notes']):
            source = self._binding(context, 'step', str(index))
            position = source.evidence['metadata'].get('step_index')
            if position is None:
                raise ValueError('Missing canonical step position: ' + note)
            yield ScopedStepOccurrence(context.operation_identity, int(position), index, source,
                record['transition_targets'].get(note, {}),
                tuple(calls_by_step.get(note, [])))

    def calls(self, context):
        """Return occurrence-qualified calls, including unresolved evidence without guessing."""
        return tuple(self._context(context)['calls'])

    def java_resolution(self, context):
        """Return Mapper candidates; this does not establish loaded-classpath origin."""
        return self._context(context).get('java_resolution', [])

    def context_evidence(self, context):
        """Return the stored consuming-context record, never a caller-supplied projection."""
        return self._context(context)

    def channel_evidence(self, context):
        """Return the immutable intake snapshot of consuming-channel mappings/import order."""
        self._context(context)
        row = self.conn.execute('''SELECT record_json FROM scoped_channel_evidence
            WHERE run_id=? AND channel=?''', (self.run_id, context.channel)).fetchone()
        if not row:
            raise ValueError('Missing consuming-channel mapping evidence: ' + context.channel)
        return json.loads(row[0])

    def canonical_steps(self, context):
        """Read all canonical source steps for selection cross-checking, including exclusions."""
        operation = self.resource(context, 'operations:' + context.operation_id)
        rows = self.conn.execute('''SELECT record_json FROM scoped_entity_usages
            WHERE run_id=? AND operation_identity=? AND json_extract(record_json,'$.kind')='opStep' ''',
            (self.run_id, operation.evidence['operation_identity'])).fetchall()
        records = [json.loads(row[0]) for row in rows]
        records.sort(key=lambda record: int(record['metadata']['step_index']))
        return [self._reference(record) for record in records]

    def nested_definition(self, context, resource, selector):
        """Find a nested definition only inside a selected canonical resource's source scope."""
        self._context(context)
        bound = self.conn.execute('''SELECT d.record_json FROM scoped_source_definitions d
            JOIN scoped_context_bindings b ON b.run_id=d.run_id AND b.definition_id=d.definition_id
            WHERE d.run_id=? AND b.operation_identity=? AND d.definition_id=? LIMIT 1''',
            (self.run_id, context.operation_identity, resource.definition_id)).fetchone()
        if not bound:
            raise ValueError('Nested definition owner is not selected in this execution context')
        owner = json.loads(bound[0])
        if not selector.startswith(owner['source_selector'] + '/'):
            raise ValueError('Nested selector escapes its selected owner')
        rows = self.conn.execute('''SELECT record_json FROM scoped_source_definitions
            WHERE run_id=? AND kind='format' AND json_extract(record_json,'$.source_relative_path')=?
            AND json_extract(record_json,'$.source_selector')=?''',
            (self.run_id, owner['source_relative_path'], selector)).fetchall()
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous nested definition: ' + selector)
        return self._reference(json.loads(rows[0][0]))

    def java_candidate(self, context, fqcn, relative_path):
        """Read a candidate only when this consuming context explicitly records its origin."""
        candidates = [candidate for item in self.java_resolution(context) if item.get('fqcn') == fqcn
                      for candidate in item.get('candidates', []) if candidate['source_relative_path'] == relative_path]
        if len(candidates) != 1:
            raise ValueError('Missing or ambiguous contextual Java origin: ' + fqcn)
        row = self.conn.execute('''SELECT record_json FROM scoped_source_definitions
            WHERE run_id=? AND definition_id=? AND kind='java_class' ''',
            (self.run_id, candidates[0]['definition_id'])).fetchone()
        if not row:
            raise ValueError('Contextual Java candidate has no canonical source definition: ' + fqcn)
        record = json.loads(row[0])
        if record['entity_id'] != fqcn or record['source_relative_path'] != relative_path:
            raise ValueError('Contextual Java candidate coordinates disagree: ' + fqcn)
        return self._reference(record)

    def captured_java_dependency(self, context, fqcn, relative_path):
        """Read an exact captured source coordinate after the caller proves project visibility.

        This is source evidence for explicit production-project selections and
        syntax-discovered helpers, not a name-based fallback or an assertion
        that the class is loaded by Composer.
        """
        self._context(context)
        rows = self.conn.execute('''SELECT record_json FROM scoped_source_definitions
            WHERE run_id=? AND kind='java_class' AND logical_id=?
            AND json_extract(record_json,'$.source_relative_path')=?''',
            (self.run_id, fqcn, relative_path)).fetchall()
        if len(rows) != 1:
            raise ValueError('Java dependency source was not uniquely captured by intake: ' + relative_path)
        return self._reference(json.loads(rows[0][0]))

    def captured_java_revisions(self, context):
        """Yield compact original-source revisions for dependency verification, without note bodies."""
        self._context(context)
        for row in self.conn.execute('''SELECT json_extract(record_json,'$.source_relative_path'),source_hash
            FROM scoped_source_definitions WHERE run_id=? AND kind='java_class' ''', (self.run_id,)):
            yield row[0], row[1]

    @staticmethod
    def _reference(record):
        return ScopedEntityReference(*(record[field] for field in
            ('definition_id', 'usage_id', 'kind', 'entity_id', 'note')), evidence=record)
