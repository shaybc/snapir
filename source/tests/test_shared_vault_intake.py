"""Validate schema-three inventory publication and qualified access independently of conversion."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.state_store_tools.db import get_connection, create_all_tables


def fixture_vault(tmp_path):
    vault = tmp_path / 'vault'
    entries = []

    def note(kind, name, path, **fields):
        identity = 'definition-' + str(len(entries))
        entry = dict(kind=kind, entity_id=name, definition_id=identity, usage_id='usage-' + identity,
                     note=path, source_relative_path='Channel/XML/common.xml',
                     source_selector='/XML[1]/' + identity, source_hash='source-hash', **fields)
        content = '# ' + name + '\n\n---\n' + '\n'.join(f'{k}: {v}' for k, v in dict(
            entity_id=name, qualified_entity_id=identity, usage_id=entry['usage_id'],
            operation_identity=fields.get('operation_identity', ''),
            channel=fields.get('channel', ''), step_index=fields.get('step_index', '')).items()) + '\n---\n'
        if kind == 'opStep':
            content += '\n## Parameters\n- fieldValue: ' + str(fields['step_index']) + '\n'
        target = vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
        entry['note_hash'] = hashlib.sha256(target.read_bytes()).hexdigest()
        entries.append(entry)
        return entry

    operation = note('operation', '#Common', 'channels/XML/operations/#Common/operation.md',
                     channel='XML', operation_id='#Common', operation_identity='source-context')
    first = note('opStep', 'SetSITE', 'channels/XML/operations/#Common/opsteps/occurrences/1/SetSITE.md',
                 operation_identity='source-context', step_index=0)
    second = note('opStep', 'SetSite', 'channels/XML/operations/#Common/opsteps/occurrences/3/SetSite.md',
                  operation_identity='source-context', step_index=2)
    xml_format = note('format', 'Fmt', 'channels/XML/resources/Fmt%23.md')
    sme_format = note('format', 'Fmt', 'channels/SME/resources/Fmt%23.md')
    contexts = []
    for channel, fmt in [('XML', xml_format), ('SME', sme_format)]:
        contexts.append(dict(channel=channel, operation_id='#Common', operation_identity='context-' + channel,
            definition_id=operation['definition_id'], note=operation['note'],
            references={'operations:#Common': operation['note'], 'formats:Fmt': fmt['note']},
            step_notes=[first['note'], second['note']], entry_step_note=first['note'],
            transition_targets={first['note']: {'on0Do': second['note']}, second['note']: {'on0Do': first['note']}},
            calls=[], java_resolution=[{'status': 'unresolved_classpath', 'fqcn': 'example.Work'}]))
        channel_note = vault / 'channels' / channel / 'channel.md'
        channel_note.parent.mkdir(parents=True, exist_ok=True)
        channel_note.write_text(f'# Channel\n\n---\nchannel: {channel}\n---\n\n## Import Chain\n- XML\n- {channel}\n', encoding='utf-8')
    manifest = dict(vault_schema_version=3, identity_version=1, complete=True, workspace_id='fixture',
                    channels=['XML', 'SME'], entities=entries, operation_contexts=contexts, diagnostics=[])
    (vault / 'vault-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return vault, manifest


def configuration():
    return SimpleNamespace(run_id='run', run_mode=SimpleNamespace(value='single_channel'),
                           target_channels=['SME'], include_operations=None, exclude_operations=None)


def connection():
    conn = get_connection(':memory:')
    create_all_tables(conn)
    return conn


def test_context_override_order_and_literal_paths(tmp_path):
    vault, manifest = fixture_vault(tmp_path)
    conn = connection()
    messages = []
    summary = import_vault(conn, str(vault), configuration(), progress=messages.append)
    assert summary.operations == 1
    assert summary.channel_operations == 2
    assert conn.execute('SELECT channel FROM operations').fetchall()[0][0] == 'SME'
    assert conn.execute('SELECT count(*) FROM scoped_operation_contexts').fetchone()[0] == 2
    assert conn.execute('SELECT count(*) FROM source_artifacts').fetchone()[0] == 0
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='operation_service_contracts'").fetchone()
    access = ScopedVaultAccess(conn, 'run')
    sme, xml = access.operation('SME', '#Common'), access.operation('XML', '#Common')
    assert sme.definition_id == xml.definition_id
    assert access.resource(sme, 'formats:Fmt').definition_id != access.resource(xml, 'formats:Fmt').definition_id
    assert access.resource(sme, 'formats:Fmt').note.endswith('Fmt%23.md')
    steps = list(access.steps(sme))
    assert [s.source.entity_id for s in steps] == ['SetSITE', 'SetSite']
    assert [s.source_index for s in steps] == [0, 2]
    assert [s.effective_index for s in steps] == [0, 1]
    assert steps[1].source.evidence['parsed']['parameters']['fieldValue'] == '2'
    assert steps[1].transition_targets['on0Do'] == steps[0].source.note
    assert access.java_resolution(sme)[0]['status'] == 'unresolved_classpath'
    assert 'Inventory ready' in messages[-1] and 'conversion remains gated' in messages[-1]
    with pytest.raises(ValueError, match='Missing execution context'):
        access.operation('WEB', '#Common')
    with pytest.raises(ValueError, match='Missing contextual'):
        access.resource(sme, 'formats:Unknown')


def test_changed_channel_evidence_rejects_same_run_without_mutation(tmp_path):
    vault, _ = fixture_vault(tmp_path)
    conn = connection()
    import_vault(conn, str(vault), configuration())
    before = list(conn.iterdump())
    channel = vault / 'channels/SME/channel.md'
    channel.write_text(channel.read_text() + '\n## Tag Mappings\n- Fmt -> other.Class\n')
    with pytest.raises(ValueError, match='fresh run'):
        import_vault(conn, str(vault), configuration())
    assert list(conn.iterdump()) == before


def test_failed_import_rolls_back_all_inventory(tmp_path, monkeypatch):
    vault, _ = fixture_vault(tmp_path)
    conn = connection()
    before = list(conn.iterdump())
    from tools.composer_mapper_tools import shared_vault_importer
    parser = shared_vault_importer._parsed_note

    def fail(entry, text, path):
        if entry['kind'] == 'format':
            raise ValueError('simulated interruption')
        return parser(entry, text, path)

    monkeypatch.setattr(shared_vault_importer, '_parsed_note', fail)
    with pytest.raises(ValueError, match='interruption'):
        import_vault(conn, str(vault), configuration())
    assert list(conn.iterdump()) == before


@pytest.mark.parametrize('change', ['incomplete', 'note', 'context', 'channel'])
def test_invalid_evidence_never_publishes_ready_import(tmp_path, change):
    vault, manifest = fixture_vault(tmp_path)
    if change == 'incomplete':
        (vault / 'vault-generation.json').write_text('{}')
    elif change == 'note':
        (vault / manifest['entities'][0]['note']).write_text('corrupted')
    elif change == 'context':
        manifest['operation_contexts'][1]['definition_id'] = 'missing'
        (vault / 'vault-manifest.json').write_text(json.dumps(manifest))
    else:
        (vault / 'channels/SME/channel.md').unlink()
    conn = connection()
    before = list(conn.iterdump())
    with pytest.raises(ValueError):
        import_vault(conn, str(vault), configuration())
    assert list(conn.iterdump()) == before


def test_requested_context_must_exist_and_does_not_fallback(tmp_path):
    vault, _ = fixture_vault(tmp_path)
    config = configuration()
    config.target_channels = ['WEB']
    conn = connection()
    with pytest.raises(ValueError, match='execution evidence'):
        import_vault(conn, str(vault), config)


def test_manifest_hash_does_not_load_whole_file(tmp_path, monkeypatch):
    vault, _ = fixture_vault(tmp_path)
    from pathlib import Path
    original = Path.read_bytes

    def read(path):
        assert path.name != 'vault-manifest.json'
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', read)
    import_vault(connection(), str(vault), configuration())


def test_reimport_counts_and_cross_run_context_are_safe(tmp_path):
    vault, _ = fixture_vault(tmp_path)
    conn = connection()
    config = configuration()
    first = import_vault(conn, str(vault), config)
    second = import_vault(conn, str(vault), config)
    assert first.operations == second.operations == 1
    original = ScopedVaultAccess(conn, 'run').operation('SME', '#Common')
    config.run_id = 'other'
    import_vault(conn, str(vault), config)
    with pytest.raises(ValueError, match='another imported run'):
        list(ScopedVaultAccess(conn, 'other').steps(original))
    with pytest.raises(ValueError, match='another imported run'):
        ScopedVaultAccess(conn, 'other').resource(original, 'formats:Fmt')


def test_schema_two_import_and_gate_remain_supported(tmp_path):
    vault, manifest = fixture_vault(tmp_path)
    manifest['vault_schema_version'] = 2
    manifest.pop('operation_contexts')
    (vault / 'vault-manifest.json').write_text(json.dumps(manifest))
    conn = connection()
    summary = import_vault(conn, str(vault), configuration())
    assert summary.operations == 1
    assert conn.execute('SELECT schema_version FROM scoped_vault_runs').fetchone()[0] == 2
    from tools.composer_mapper_tools.scoped_vault_importer import require_qualified_conversion
    with pytest.raises(ValueError, match='conversion is gated'):
        require_qualified_conversion(conn, 'run')


def test_scoped_validators_use_contexts_without_legacy_registry(tmp_path):
    vault, _ = fixture_vault(tmp_path)
    from tools.workspace_intake_tools.vault_validator import validate_vault_structure
    from tools.workspace_intake_tools.channel_validator import validate_channel_in_registry
    assert validate_vault_structure(str(vault)) == []
    assert validate_channel_in_registry(str(vault), ['SME', 'WEB']) == ['WEB']


def test_large_inventory_is_persisted_without_whole_manifest_reads(tmp_path, monkeypatch):
    vault, manifest = fixture_vault(tmp_path)
    template = manifest['entities'][-1]
    for index in range(1500):
        entry = dict(template, definition_id=f'extra-{index}', usage_id=f'extra-usage-{index}',
                     entity_id=f'Fmt{index}', note=f'channels/XML/resources/extra/{index}.md',
                     source_selector=f'/XML[1]/fmtDef[{index + 20}]')
        body = f'# Fmt{index}\n\n---\nentity_id: {entry["entity_id"]}\nqualified_entity_id: {entry["definition_id"]}\nusage_id: {entry["usage_id"]}\n---\n'
        path = vault / entry['note']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8', newline='\n')
        entry['note_hash'] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest['entities'].append(entry)
    (vault / 'vault-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    from pathlib import Path
    original = Path.read_bytes

    def read(path):
        assert path.name != 'vault-manifest.json'
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', read)
    conn = connection()
    summary = import_vault(conn, str(vault), configuration())
    assert summary.formats == 1502
    assert conn.execute('SELECT count(*) FROM scoped_entity_usages').fetchone()[0] == 1505
    assert conn.execute('SELECT count(*) FROM scoped_operation_contexts').fetchone()[0] == 2


def test_exclusions_preserve_context_evidence_without_scheduling(tmp_path):
    vault, _ = fixture_vault(tmp_path)
    config = configuration()
    config.exclude_operations = ['#Common']
    conn = connection()
    import_vault(conn, str(vault), config)
    assert conn.execute('SELECT count(*) FROM operations').fetchone()[0] == 0
    assert ScopedVaultAccess(conn, 'run').operation('SME', '#Common').channel == 'SME'


def test_occurrence_calls_keep_resolved_and_unresolved_evidence(tmp_path):
    vault, manifest = fixture_vault(tmp_path)
    context = manifest['operation_contexts'][1]
    context['calls'] = [dict(step='SetSITE', step_note=context['step_notes'][0], target_name='#Common',
                             target_context='SME/#Common', target_definition_id=context['definition_id'],
                             target_note=context['note']),
                        dict(step='SetSite', step_note=context['step_notes'][1], target_name='Unknown',
                             detail='Missing target')]
    (vault / 'vault-manifest.json').write_text(json.dumps(manifest))
    conn = connection()
    import_vault(conn, str(vault), configuration())
    access = ScopedVaultAccess(conn, 'run')
    context = access.operation('SME', '#Common')
    first, second = list(access.steps(context))
    assert first.calls[0]['target_context'] == 'SME/#Common'
    assert second.calls[0]['detail'] == 'Missing target'
    assert len(access.calls(context)) == 2
