"""Validate portable Excel export streaming, identity checks and progress output."""

import hashlib
import io
import json
from pathlib import Path
import tracemalloc

import pytest

from tools.composer_mapper_tools.manifest_json_stream import _ManifestJsonReader, iter_manifest_fields
from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
from tools.operation_call_tools.export_progress import ExportProgress


def _scoped_vault(root, resources=3, padding=0):
    root.mkdir(exist_ok=True)
    header = dict(vault_schema_version=2, identity_version=1, producer='composer-mapper',
                  complete=True, workspace_id='fixture', channels=['XML'], diagnostics=[])
    with (root / 'vault-manifest.json').open('w', encoding='utf-8') as manifest:
        # Put the header after the array to exercise arbitrary JSON member order.
        manifest.write('{"entities":[')
        for number in range(resources + 1):
            operation = number == resources
            entry = dict(kind='operation' if operation else 'format', entity_id='A' if operation else f'Item{number}',
                         definition_id=f'definition-{number}', usage_id=f'usage-{number}', channel='XML',
                         operation_id='A' if operation else '', operation_identity='XML/A' if operation else '',
                         note=f'notes/{number}.md', source_relative_path='source.xml', source_selector=f'/XML[1]/item[{number + 1}]',
                         source_hash='source-hash')
            note = root / entry['note']
            note.parent.mkdir(exist_ok=True)
            note.write_text('# Note\n\n---\n' + '\n'.join(f'{key}: {value}' for key, value in (
                ('entity_id', entry['entity_id']), ('qualified_entity_id', entry['definition_id']),
                ('usage_id', entry['usage_id']), ('operation_identity', entry['operation_identity']), ('channel', 'XML')))
                + '\n---\n\n## Steps\n- None\n', encoding='utf-8')
            entry['note_hash'] = hashlib.sha256(note.read_bytes()).hexdigest()
            if operation:
                entry['references'] = {'operations:A': entry['note']}
            else:
                entry['unused_evidence'] = 'x' * padding
            if number:
                manifest.write(',')
            json.dump(entry, manifest)
        manifest.write('],')
        manifest.write(json.dumps(header)[1:])
    return root


def test_compact_validation_streams_inventory_with_bounded_memory(tmp_path):
    root = _scoped_vault(tmp_path, resources=250, padding=65536)
    messages = []
    tracemalloc.start()
    try:
        compact = read_vault_manifest(root, retain_inventory=False, progress=messages.append)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(compact['entities']) == 1
    assert compact['entities'][0]['entity_id'] == 'A'
    assert peak < (root / 'vault-manifest.json').stat().st_size // 2
    assert messages[0].startswith('Validated 1 notes:')
    assert any(message.startswith('Validated 250 notes:') for message in messages)
    assert messages[-1] == 'Validated 251 notes; 1 effective operations'
    full = read_vault_manifest(root)
    assert len(full['entities']) == 251
    assert full['entities'][-1] == compact['entities'][0]
    assert full['entities'][0]['unused_evidence'] == 'x' * 65536


def test_validation_hashes_and_reads_metadata_in_one_open(tmp_path, monkeypatch):
    root = _scoped_vault(tmp_path)
    original = Path.open
    opened = []

    def track(path, *args, **kwargs):
        if path.suffix == '.md':
            opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', track)
    assert len(read_vault_manifest(root)['entities']) == 4
    assert len(opened) == len(set(opened)) == 4


@pytest.mark.parametrize('retain', [False, True])
@pytest.mark.parametrize('failure', ['hash', 'missing', 'path', 'usage', 'escape', 'channel', 'schema', 'incomplete'])
def test_streamed_reader_keeps_validation_guards(tmp_path, retain, failure):
    root = _scoped_vault(tmp_path)
    path = root / 'vault-manifest.json'
    manifest = json.loads(path.read_text())
    first, second, operation = manifest['entities'][0], manifest['entities'][1], manifest['entities'][-1]
    if failure == 'hash':
        (root / first['note']).write_text('changed')
    elif failure == 'missing':
        (root / first['note']).unlink()
    elif failure == 'path':
        first['note'] = '../outside.md'
    elif failure == 'usage':
        second['usage_id'] = first['usage_id']
    elif failure == 'escape':
        operation['references'] = {'formats:Item0': first['note']}
    elif failure == 'channel':
        operation['channel'] = 'IVR'
    elif failure == 'schema':
        manifest['vault_schema_version'] = 99
    else:
        (root / 'vault-generation.json').write_text('{}')
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        read_vault_manifest(root, retain_inventory=retain)


def test_streamed_metadata_retains_bom_crlf_and_unicode_support(tmp_path):
    root = _scoped_vault(tmp_path, resources=0)
    path = root / 'vault-manifest.json'
    manifest = json.loads(path.read_text())
    entry = manifest['entities'][0]
    note = root / entry['note']
    content = note.read_text(encoding='utf-8') + '\nשלום 😀\n'
    note.write_bytes(b'\xef\xbb\xbf' + content.replace('\n', '\r\n').encode())
    entry['note_hash'] = hashlib.sha256(note.read_bytes()).hexdigest()
    path.write_bytes(b'\xef\xbb\xbf' + json.dumps(manifest).encode())
    assert read_vault_manifest(root)['entities'][0] == entry


@pytest.mark.parametrize('text', [
    '', '[]', '{', '{"entities":[{}', '{"entities":[],}',
    '{"entities":[{},]}', '{"entities":[]} trailing', '{"n":1e}',
])
def test_streamed_json_rejects_malformed_or_truncated_input(tmp_path, text):
    path = tmp_path / 'manifest.json'
    path.write_text(text)
    with pytest.raises(ValueError):
        list(iter_manifest_fields(path))


def test_streamed_json_handles_values_across_small_chunk_boundaries():
    class SmallChunks(io.StringIO):
        def read(self, size=-1):
            assert size == 65536
            return super().read(1)

    expected = {'text': 'שלום 😀 " \\ \n', 'number': -1.234e20, 'values': [True, False, None, {}, []]}
    reader = _ManifestJsonReader(SmallChunks(json.dumps(expected)))
    assert reader.value() == expected
    assert reader.peek() == ''
    number = _ManifestJsonReader(SmallChunks('123.45e-10 '))
    assert number.value() == 123.45e-10


def test_progress_is_throttled_and_includes_total_elapsed(monkeypatch, capsys):
    import tools.operation_call_tools.export_progress as module
    now = [100.0]
    monkeypatch.setattr(module, 'monotonic', lambda: now[0])
    progress = ExportProgress()
    progress.phase('Validating vault')
    assert 'elapsed=00:00:00' in capsys.readouterr().out
    progress.update('Too soon')
    assert capsys.readouterr().out == ''
    now[0] += 5
    progress.update('Validated 250 notes')
    assert 'Validated 250 notes | elapsed=00:00:05' in capsys.readouterr().out
    now[0] += 3600
    assert progress.elapsed() == '01:00:05'
