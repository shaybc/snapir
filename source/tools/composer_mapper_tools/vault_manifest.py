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


def read_vault_manifest(vault, *, retain_inventory=True, progress=None, allow_shared=False):
    """Return a validated manifest, or None for a legacy vault.

    Shared schema-three notes require explicit opt-in; converter readers stay schema two.

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
            if field == 'vault_schema_version' and entry == 3 and not allow_shared:
                raise ValueError('Shared schema-three vault requires an updated consumer; converter support is not implemented')
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
    if manifest.get('vault_schema_version') not in (2, 3) or manifest.get('identity_version') != 1:
        raise ValueError('Unsupported vault schema or identity version')
    shared = manifest['vault_schema_version'] == 3
    if shared and not allow_shared:
        raise ValueError('Shared schema-three vault requires an updated consumer; converter support is not implemented')
    if manifest.get('complete') is not True or not manifest.get('workspace_id'):
        raise ValueError('Incomplete scoped vault manifest')
    if not isinstance(manifest.get('entities'), list):
        raise ValueError('Missing scoped entity inventory')
    for entry in operations:
        for reference in entry.get('references', {}).values():
            if reference.casefold() not in paths or not shared and paths[reference.casefold()] != entry['operation_identity']:
                raise ValueError('Reference escapes owning operation view: ' + reference)
    if shared:
        _validate_operation_contexts(manifest, paths, operations)
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


def _validate_operation_contexts(manifest, paths, operations):
    """Validate contextual connections against canonical notes and resolved call targets."""
    contexts = manifest.get('operation_contexts')
    if not isinstance(contexts, list):
        raise ValueError('Missing consuming-channel operation connections')
    definitions = {entry['definition_id']: entry for entry in operations}
    by_key = {}
    for context in contexts:
        if not isinstance(context, dict) or any(not isinstance(context.get(key), str) or not context[key]
                for key in ('channel', 'operation_id', 'operation_identity', 'definition_id', 'note')):
            raise ValueError('Invalid operation connection identity')
        key = context['channel'] + '/' + context['operation_id']
        if key in by_key:
            raise ValueError('Duplicate consuming-channel operation connection: ' + key)
        by_key[key] = context
        definition = definitions.get(context['definition_id'])
        if definition is None or definition['note'] != context['note'] or definition['entity_id'] != context['operation_id']:
            raise ValueError('Connection refers to an invalid canonical operation: ' + key)
        references = context.get('references')
        steps = context.get('step_notes')
        if not isinstance(references, dict) or not isinstance(steps, list):
            raise ValueError('Missing resolved dependencies: ' + key)
        if references.get('operations:' + context['operation_id']) != context['note']:
            raise ValueError('Invalid contextual operation reference: ' + key)
        for note in [*references.values(), *steps]:
            if not isinstance(note, str) or note.casefold() not in paths:
                raise ValueError('Missing canonical dependency note: ' + str(note))
        for note in steps:
            if paths[note.casefold()] != definition['operation_identity']:
                raise ValueError('Context step belongs to another source operation: ' + note)
        if context.get('entry_step_note', '') != (steps[0] if steps else ''):
            raise ValueError('Invalid contextual entry step: ' + key)
        transitions = context.get('transition_targets')
        if not isinstance(transitions, dict) or any(note not in steps or not isinstance(targets, dict)
                or any(target not in steps for target in targets.values()) for note, targets in transitions.items()):
            raise ValueError('Invalid contextual transition targets: ' + key)
        if not isinstance(context.get('calls'), list):
            raise ValueError('Missing contextual operation calls: ' + key)
    for key, context in by_key.items():
        for call in context['calls']:
            if not isinstance(call, dict) or call.get('step_note') not in context['step_notes']:
                raise ValueError('Invalid contextual call step: ' + key)
            if call.get('detail'):
                continue
            target = by_key.get(call.get('target_context'))
            if target is None or target['channel'] != context['channel'] or target['note'] != call.get('target_note') \
                    or target['definition_id'] != call.get('target_definition_id') or target['operation_id'] != call.get('target_name'):
                raise ValueError('Invalid resolved operation call: ' + key)
