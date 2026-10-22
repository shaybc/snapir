"""Validate scoped vault identity and enumerate notes without guessing folder depth."""

import hashlib
import codecs
import re
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
from tools.composer_mapper_tools.manifest_json_stream import iter_manifest_fields


def _read_note_metadata(candidate):
    """Hash and validate UTF-8 in one buffered read, retaining only the frontmatter."""
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8-sig')()
    header, metadata = '', None
    with candidate.open('rb') as note:
        while chunk := note.read(65536):
            digest.update(chunk)
            text = decoder.decode(chunk)
            if metadata is None:
                header += text
                match = re.search(r'(?s)(?:^|\n)---\r?\n.*?\r?\n---\r?\n', header)
                if match:
                    metadata = parse_frontmatter(header[:match.end()].replace('\r\n', '\n').replace('\r', '\n'))
                    header = ''
        tail = decoder.decode(b'', final=True)
    if metadata is None:
        metadata = parse_frontmatter((header + tail).replace('\r\n', '\n').replace('\r', '\n'))
    return metadata, digest.hexdigest()


def read_vault_manifest(vault, *, retain_inventory=True, progress=None):
    """Return a validated schema-two manifest, or None for a legacy vault.

    Incomplete generation, unknown schemas, conflicting views and escaped paths are errors.
    Exporters can discard non-operation records after validation with retain_inventory=False.
    Compact identity indexes remain in memory; JSON and note bodies are read incrementally.
    Other callers retain the full manifest by default. Progress callbacks receive text only.
    This reader uses only Python's standard library so standalone exporters can bundle it.
    """
    root = Path(vault).resolve()
    path = root / 'vault-manifest.json'
    if (root / 'vault-generation.json').exists():
        raise ValueError('Incomplete scoped vault generation: ' + str(root))
    if not path.exists():
        if (root / 'channels').exists() and list((root / 'channels').glob('*/operations/*/operation.md')):
            raise ValueError('Scoped vault is missing vault-manifest.json')
        return None
    manifest = {}
    paths, usages, definitions = {}, set(), {}
    operations = []
    processed = 0
    for field, event, entry in iter_manifest_fields(path):
        if event == 'array':
            manifest[field] = []
            continue
        if event == 'value':
            manifest[field] = entry
            continue
        if field != 'entities':
            manifest[field].append(entry)
            continue
        processed += 1
        required = ('kind', 'entity_id', 'definition_id', 'usage_id', 'note', 'source_relative_path', 'source_selector', 'source_hash', 'note_hash')
        if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key] for key in required):
            raise ValueError('Invalid scoped entity identity')
        relative = entry['note']
        candidate = (root / relative).resolve()
        if '\\' in relative or Path(relative).is_absolute() or not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError('Missing or unsafe scoped note path: ' + relative)
        if relative.casefold() in paths or entry['usage_id'] in usages:
            raise ValueError('Duplicate scoped note path or usage identity: ' + relative)
        metadata, note_hash = _read_note_metadata(candidate)
        if note_hash != entry['note_hash']:
            raise ValueError('Scoped note differs from completed manifest: ' + relative)
        for field, key in (('entity_id', 'entity_id'), ('qualified_entity_id', 'definition_id'), ('usage_id', 'usage_id')):
            if str(metadata.get(field, '')) != entry[key]:
                raise ValueError('Scoped note and manifest identity disagree: ' + relative)
        if str(metadata.get('operation_identity') or '') != entry.get('operation_identity', ''):
            raise ValueError('Scoped note belongs to another operation view: ' + relative)
        coordinates = tuple(entry[key] for key in ('kind', 'entity_id', 'source_relative_path', 'source_selector', 'source_hash'))
        previous = definitions.setdefault(entry['definition_id'], coordinates)
        if previous != coordinates:
            raise ValueError('Conflicting views of source definition: ' + entry['definition_id'])
        paths[relative.casefold()] = entry.get('operation_identity')
        usages.add(entry['usage_id'])
        if retain_inventory or entry['kind'] == 'operation' and entry.get('operation_id'):
            manifest['entities'].append(entry)
        if progress and (processed == 1 or processed % 250 == 0):
            progress(f'Validated {processed} notes: {relative}')
        if entry['kind'] != 'operation' or not entry.get('operation_id'):
            continue
        if entry['operation_id'] != entry['entity_id'] or not entry.get('channel') or not entry.get('operation_identity'):
            raise ValueError('Invalid effective operation identity: ' + entry['note'])
        if str(metadata.get('channel', '')) != entry['channel']:
            raise ValueError('Scoped operation channel and manifest disagree: ' + entry['note'])
        operations.append(entry)
    if manifest.get('vault_schema_version') != 2 or manifest.get('identity_version') != 1:
        raise ValueError('Unsupported vault schema or identity version')
    if manifest.get('complete') is not True or not manifest.get('workspace_id'):
        raise ValueError('Incomplete scoped vault manifest')
    if not isinstance(manifest.get('entities'), list):
        raise ValueError('Missing scoped entity inventory')
    for entry in operations:
        for reference in entry.get('references', {}).values():
            if reference.casefold() not in paths or paths[reference.casefold()] != entry['operation_identity']:
                raise ValueError('Reference escapes owning operation view: ' + reference)
    if progress:
        progress(f'Validated {processed} notes; {len(operations)} effective operations')
    return manifest


def operation_note_paths(vault, manifest=None):
    """Enumerate effective operation notes from a scoped manifest or legacy folders."""
    root = Path(vault).resolve()
    manifest = read_vault_manifest(root) if manifest is None else manifest
    if manifest is not None:
        return [root / entry['note'] for entry in manifest['entities']
                if entry['kind'] == 'operation' and entry.get('operation_id')]
    if not (root / 'operations').is_dir():
        raise ValueError('Missing operations folder: ' + str(root))
    return sorted((root / 'operations').rglob('*.md'))
