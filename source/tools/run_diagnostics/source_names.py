"""Resolve captured evidence identities to saved source filenames without opening sources."""

import json
from pathlib import Path, PurePosixPath
import re
import sqlite3


def source_names(directory, payload):
    """Combine map filenames and request provenance; ambiguous identities stay unresolved."""
    candidates = {}
    def add(identity, path):
        if identity and isinstance(path, str) and path:
            candidates.setdefault(str(identity), set()).add(path.replace('\\', '/'))
    vault = directory / 'vault'
    database = directory / 'state/migration.db'
    if database.is_file():
        try:
            with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                row = conn.execute('SELECT run_config_json FROM runs WHERE run_id=?', (directory.name,)).fetchone()
                if row:
                    vault = Path(json.loads(row[0]).get('vault_root') or vault)
        except (sqlite3.Error, ValueError, TypeError):
            pass
    profile = directory / 'state/profile.json'
    if vault == directory / 'vault' and profile.is_file():
        try:
            vault = Path(json.loads(profile.read_text(encoding='utf-8-sig')).get('existing_composer_map') or vault)
        except (OSError, ValueError):
            pass
    analysis = vault / 'analysis/analysis.sqlite'
    if analysis.is_file():
        try:
            with sqlite3.connect(analysis.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                for identity, path in conn.execute('SELECT definition,source_relative_path FROM notes'):
                    add(identity, path)
        except sqlite3.Error:
            pass
    def visit(value):
        if isinstance(value, dict):
            path = value.get('source_relative_path') or value.get('source_file') or value.get('path')
            add(value.get('definition_id') or value.get('identity') or value.get('original_identity'), path)
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(payload)
    # Absolute provenance and map-relative paths can name the same file.
    result = {}
    for identity, paths in candidates.items():
        relative = [path for path in paths if not path.startswith('/') and not re.match(r'^[A-Za-z]:', path)]
        choices = relative or list(paths)
        if len(choices) == 1 and all(path == choices[0] or path.endswith('/' + choices[0]) for path in paths):
            result[identity] = choices[0]
    return result


def export_source_path(value, names, number):
    """Return a safe relative export path and the resolved original path, if available."""
    identity = str(value.get('original_identity') or value.get('identity') or '')
    original = value.get('path') or value.get('source_relative_path') or value.get('source_file') or names.get(identity)
    if not original:
        label = re.sub(r'[^A-Za-z0-9_-]', '_', identity[:64]) or 'embedded'
        return Path('unresolved') / f'{number:05d}-{label}.txt', None
    normalized = str(original).replace('\\', '/')
    parts = list(PurePosixPath(normalized).parts)
    if normalized.startswith('/') or re.match(r'^[A-Za-z]:', normalized):
        parts = parts[parts.index('src') + 1:] if 'src' in parts else parts[-1:]
    parts = [re.sub(r'[^A-Za-z0-9._-]', '_', part) for part in parts if part not in ('/', '.', '..')]
    return Path(*parts) if parts else Path(f'{number:05d}-embedded.txt'), str(original)
