"""Validate scoped vault identity and enumerate notes without guessing folder depth."""

import hashlib
import json
from pathlib import Path

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter


def read_vault_manifest(vault):
    """Return a validated schema-two manifest, or None for a legacy vault.

    Incomplete generation, unknown schemas, conflicting views and escaped paths are errors.
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
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(manifest, dict):
        raise ValueError('Invalid scoped vault manifest')
    if manifest.get('vault_schema_version') != 2 or manifest.get('identity_version') != 1:
        raise ValueError('Unsupported vault schema or identity version')
    if manifest.get('complete') is not True or not manifest.get('workspace_id'):
        raise ValueError('Incomplete scoped vault manifest')
    entries = manifest.get('entities')
    if not isinstance(entries, list):
        raise ValueError('Missing scoped entity inventory')
    paths, usages, definitions = {}, set(), {}
    for entry in entries:
        required = ('kind', 'entity_id', 'definition_id', 'usage_id', 'note', 'source_relative_path', 'source_selector', 'source_hash', 'note_hash')
        if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key] for key in required):
            raise ValueError('Invalid scoped entity identity')
        relative = entry['note']
        candidate = (root / relative).resolve()
        if '\\' in relative or Path(relative).is_absolute() or not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError('Missing or unsafe scoped note path: ' + relative)
        if relative.casefold() in paths or entry['usage_id'] in usages:
            raise ValueError('Duplicate scoped note path or usage identity: ' + relative)
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != entry['note_hash']:
            raise ValueError('Scoped note differs from completed manifest: ' + relative)
        metadata = parse_frontmatter(candidate.read_text(encoding='utf-8-sig'))
        for field, key in (('entity_id', 'entity_id'), ('qualified_entity_id', 'definition_id'), ('usage_id', 'usage_id')):
            if str(metadata.get(field, '')) != entry[key]:
                raise ValueError('Scoped note and manifest identity disagree: ' + relative)
        if str(metadata.get('operation_identity') or '') != entry.get('operation_identity', ''):
            raise ValueError('Scoped note belongs to another operation view: ' + relative)
        coordinates = tuple(entry[key] for key in ('kind', 'entity_id', 'source_relative_path', 'source_selector', 'source_hash'))
        previous = definitions.setdefault(entry['definition_id'], coordinates)
        if previous != coordinates:
            raise ValueError('Conflicting views of source definition: ' + entry['definition_id'])
        paths[relative.casefold()] = entry
        usages.add(entry['usage_id'])
    for entry in entries:
        if entry['kind'] != 'operation' or not entry.get('operation_id'):
            continue
        if entry['operation_id'] != entry['entity_id'] or not entry.get('channel') or not entry.get('operation_identity'):
            raise ValueError('Invalid effective operation identity: ' + entry['note'])
        metadata = parse_frontmatter((root / entry['note']).read_text(encoding='utf-8-sig'))
        if str(metadata.get('channel', '')) != entry['channel']:
            raise ValueError('Scoped operation channel and manifest disagree: ' + entry['note'])
        for reference in entry.get('references', {}).values():
            target = paths.get(reference.casefold())
            if target is None or target.get('operation_identity') != entry['operation_identity']:
                raise ValueError('Reference escapes owning operation view: ' + reference)
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
