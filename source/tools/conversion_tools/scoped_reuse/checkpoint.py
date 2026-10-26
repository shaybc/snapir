"""Reject stale scoped checkpoints before any saved work can be reused."""

import json
from pathlib import Path

from models.scoped_checkpoint import ScopedCheckpoint
from tools.conversion_tools.scoped_reuse import state
from tools.conversion_tools.scoped_reuse.evidence import source_layout, channel_layout, context_facts, input_files, call_bindings
from tools.conversion_tools.scoped_reuse.fingerprints import POLICY_VERSION, digest, revision, conversion_policy, classpath_fingerprint


class ScopedCheckpointStale(ValueError):
    """A saved context requires explicit refreshed intake and replanning."""

    def __init__(self, affected):
        self.affected = affected
        super().__init__('Scoped checkpoint is stale; start a fresh intake/run and replan: ' +
                         '; '.join(key + ': ' + ', '.join(value) for key, value in sorted(affected.items())))


def observe_inputs(conn, config, profile, classpath):
    """Capture current common proof once per check, without caching filesystem revisions."""
    row = conn.execute('SELECT schema_version,workspace_id,manifest_hash FROM scoped_vault_runs WHERE run_id=?',
                       (config.run_id,)).fetchone()
    evidence = conn.execute('SELECT identity_version,record_json FROM scoped_intake_evidence WHERE run_id=?',
                            (config.run_id,)).fetchone()
    intake = json.loads(evidence[1])
    from tools.source_discovery_tools import discover_java_sources
    index = discover_java_sources(config.source_root)
    from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project
    channels = [item[0] for item in conn.execute(
        'SELECT DISTINCT channel FROM scoped_operation_contexts WHERE run_id=? AND selected=1', (config.run_id,))]
    allowed, pending = set(), [scoped_source_project(profile, channel) for channel in channels]
    while pending:
        project = pending.pop()
        if project in allowed:
            continue
        allowed.add(project)
        pending.extend(index.project_references.get(project, []))
    structure = dict(roots={name: paths for name, paths in index.source_roots.items() if name in allowed},
        references={name: refs for name, refs in index.project_references.items() if name in allowed},
        classes={name: [path for path in paths if index.class_projects[path] in allowed]
                 for name, paths in index.classes.items() if any(index.class_projects[path] in allowed for path in paths)},
        issues=index.issues)
    selection = {name: getattr(config, name).value if hasattr(getattr(config, name), 'value') else getattr(config, name)
                 for name in ('run_mode', 'target_channels', 'include_operations', 'exclude_operations') if hasattr(config, name)}
    if selection.get('run_mode') == 'full_inventory':
        selection.pop('target_channels', None)
    return dict(version=POLICY_VERSION, imported_schema=row[0], identity_version=evidence[0], workspace_id=row[1],
        manifest_hash=row[2], current_manifest=revision(Path(config.vault_root) / 'vault-manifest.json'),
        generation_in_progress=(Path(config.vault_root) / 'vault-generation.json').exists(),
        source_root=str(Path(config.source_root).resolve()), vault_root=str(Path(config.vault_root).resolve()),
        output_root=str(Path(config.output_root).resolve()) if getattr(config, 'output_root', None) else None,
        artifact_schema=getattr(config, 'artifact_schema_version', None), run_schema=getattr(config, 'schema_version', None),
        target_languages=[getattr(item, 'value', item) for item in getattr(config, 'target_languages', ())], selection=selection,
        intake_hash=digest(intake), policy=conversion_policy(profile), classpath=classpath_fingerprint(classpath),
        source_index=digest(structure), layout=source_layout(config.source_root), intake=intake)


def context_inputs(conn, config, identity, common, files):
    """Describe one actual consumer, preserving file-level granularity."""
    facts = context_facts(conn, config.run_id, identity)
    if facts is None or not facts['channel_evidence']:
        raise ValueError('Imported consuming context is missing')
    channel = facts['channel_evidence']
    note = Path(config.vault_root) / channel['note']
    notes = {path: revision(path) for path, _ in facts['usages']}
    return dict(common={key: value for key, value in common.items() if key not in ('layout', 'intake')},
        context_hash=digest(facts), channel_note=revision(note), notes=notes,
        layout=digest(channel_layout(common['layout'], facts['channel'], channel['markdown'])),
        call_bindings=call_bindings(conn, config.run_id, facts['channel'] + '/' + facts['operation_id']), files=files)


def _validate_checkpoints(conn, config, profile, classpath, selected):
    """Invalidate exact consumers and non-published callers; refuse selected stale work.

    Invalidation is sticky. Restoring bytes does not silently reaccept a checkpoint.
    The caller owns transaction commit so rollback cannot hide persisted stale status.
    """
    records = state.checkpoints(conn, config.run_id)
    try:
        common = observe_inputs(conn, config, profile, classpath)
    except (ValueError, OSError) as exc:
        for saved in records.values():
            state.invalidate(conn, config.run_id, saved, [str(exc)])
        raise ScopedCheckpointStale({key: [str(exc)] for key in selected}) from exc
    baseline = common['intake'].get('source_layout')
    if not baseline or baseline.get('status') != 'captured':
        for saved in records.values():
            state.invalidate(conn, config.run_id, saved, ['Intake lacks C5 source-layout proof'])
        raise ScopedCheckpointStale({key: ['Intake lacks C5 source-layout proof'] for key in selected})
    changed = {}
    for identity, saved in records.items():
        reasons = []
        if digest(dict(inputs=saved.inputs, units=saved.units, dependencies=saved.dependencies)) != saved.fingerprint:
            reasons.append('Checkpoint proof metadata changed')
        try:
            current_files = {path: revision(path) for path in saved.inputs['files']}
            current = context_inputs(conn, config, identity, common, current_files)
            for key in saved.inputs:
                if digest(current.get(key)) != digest(saved.inputs[key]):
                    reasons.append('Changed ' + key)
        except ValueError as exc:
            reasons.append(str(exc))
        if saved.status == 'stale':
            reasons.append('Previously invalidated checkpoint')
        if reasons:
            changed[identity] = reasons
    # An unprepared context must still match the source origin and channel registry at intake.
    for key in selected:
        channel, operation = key.split('/', 1)
        row = conn.execute('SELECT operation_identity FROM scoped_operation_contexts WHERE run_id=? AND channel=? AND operation_id=?',
                           (config.run_id, channel, operation)).fetchone()
        facts = context_facts(conn, config.run_id, row[0]) if row else None
        if facts is None:
            continue
        if not facts['channel_evidence']:
            changed.setdefault(row[0], []).append('Channel snapshot is missing')
            continue
        expected = channel_layout(baseline, channel, facts['channel_evidence']['markdown'])
        actual = channel_layout(common['layout'], channel, facts['channel_evidence']['markdown'])
        if Path(common['intake']['source_root']).resolve() != Path(config.source_root).resolve() or expected != actual:
            changed.setdefault(row[0], []).append('Source origin, channel registry, or project layout differs from intake')
        if any(common['intake'].get(name) != value for name, value in common['selection'].items()):
            changed.setdefault(row[0], []).append('Conversion selection differs from intake')
        if common['current_manifest'] != common['manifest_hash']:
            changed.setdefault(row[0], []).append('Vault manifest changed since intake')
        if common['generation_in_progress']:
            changed.setdefault(row[0], []).append('Vault generation is in progress')
        channel_note = facts['channel_evidence']
        if revision(Path(config.vault_root) / channel_note['note']) != channel_note['note_hash']:
            changed.setdefault(row[0], []).append('Channel note changed since intake')
        if any(revision(path) != json.loads(record)['note_hash'] for path, record in facts['usages']):
            changed.setdefault(row[0], []).append('Canonical note changed since intake')
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='scoped_workflow_preparations'").fetchone()
    old = conn.execute('SELECT preparation_json FROM scoped_workflow_preparations WHERE run_id=?', (config.run_id,)).fetchone() if table else None
    if old and json.loads(old[0]).get('schema_version') != 'scoped-v3-c5':
        for saved in records.values():
            state.invalidate(conn, config.run_id, saved, ['Preparation predates qualified C5 checkpoints'])
        raise ScopedCheckpointStale({key: ['Preparation predates qualified C5 checkpoints'] for key in selected})
    propagated = True
    while propagated:
        propagated = False
        for identity, saved in records.items():
            if identity not in changed and any(target in changed for target in saved.dependencies):
                changed[identity] = ['Changed selected called context']
                propagated = True
    affected = {}
    for identity, reasons in changed.items():
        saved = records.get(identity)
        if saved:
            state.invalidate(conn, config.run_id, saved, reasons)
            key = saved.operation_key
        else:
            row = conn.execute('SELECT channel,operation_id FROM scoped_operation_contexts WHERE run_id=? AND operation_identity=?',
                               (config.run_id, identity)).fetchone()
            key = row[0] + '/' + row[1]
        if key in selected:
            affected[key] = reasons
    if affected:
        raise ScopedCheckpointStale(affected)
    return common


def validate_checkpoints(conn, config, profile, classpath, selected):
    """Publish sticky invalidation atomically, respecting a caller's outer transaction."""
    conn.execute('SAVEPOINT scoped_checkpoint_validation')
    try:
        result = _validate_checkpoints(conn, config, profile, classpath, selected)
    except ScopedCheckpointStale:
        conn.execute('RELEASE SAVEPOINT scoped_checkpoint_validation')
        raise
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT scoped_checkpoint_validation')
        conn.execute('RELEASE SAVEPOINT scoped_checkpoint_validation')
        raise
    conn.execute('RELEASE SAVEPOINT scoped_checkpoint_validation')
    return result


def make_checkpoints(conn, config, report, closures, common):
    """Build proof for prepared contexts only; blocked analysis grants no reusable status."""
    records = []
    for key, item in report['operations'].items():
        if item['status'] != 'prepared':
            continue
        closure = closures[key]
        files = input_files(closure, config.source_root)
        inputs = context_inputs(conn, config, closure.operation_identity, common, files)
        if any(revision(path) != value for path, value in files.items()):
            raise ScopedCheckpointStale({key: ['Source changed during preparation']})
        dependencies = [closures[call['callee']].operation_identity for call in item['calls']
                        if not call['service_contract'].get('published_api') and call['callee'] in closures]
        units = {unit['unit_id']: unit['fingerprint'] for unit in item['units']}
        facts = dict(inputs=inputs, units=units, dependencies=dependencies)
        records.append(ScopedCheckpoint(operation_identity=closure.operation_identity, operation_key=key,
            fingerprint=digest(facts), inputs=inputs, units=units, dependencies=dependencies))
    return records
