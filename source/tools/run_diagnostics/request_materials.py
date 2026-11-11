"""Export saved oversized request materials without reading original workspace sources."""

import hashlib
import json
from pathlib import Path
import re

from tools.run_diagnostics.source_names import source_names, export_source_path


def export_request_materials(directory, project):
    """Copy exact captures and extract embedded text with an occurrence manifest."""
    directory, project = Path(directory).resolve(), Path(project).resolve()
    captures = directory / 'reports/oversized_model_requests'
    destination = project / 'work/diagnostics' / directory.name
    count = 0
    for capture in sorted(captures.iterdir()) if captures.is_dir() else []:
        if not re.fullmatch(r'[0-9a-f]{64}', capture.name) or capture.is_symlink() or not capture.is_dir():
            continue
        names = ('request.json', 'instructions.txt', 'metadata.json')
        if any(not (capture / name).is_file() or (capture / name).is_symlink() for name in names):
            continue
        raw = (capture / 'request.json').read_bytes()
        payload = json.loads(raw.decode('utf-8', errors='surrogatepass'))
        folder = destination / capture.name
        if folder.is_symlink():
            raise ValueError('Diagnostic destination must not be a symbolic link')
        folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            target = folder / name
            if target.is_symlink():
                raise ValueError('Diagnostic file must not be a symbolic link')
            target.write_bytes((capture / name).read_bytes())
        export_embedded_materials(directory, payload, folder)
        count += 1
    if count:
        return [f'Oversized request captures exported: {count}', 'Request materials folder: ' + str(destination),
                'Each capture includes request.json, instructions.txt, metadata.json, sources/ with resolved filenames, and materials.json.',
                'Unresolved names use sources/unresolved/*.txt; conflicting content is retained under occurrences/.',
                'Budget-check captures were intended requests, not sent model calls. Repeated content remains visible in the manifest.']
    return ['No exact oversized request captures are available for this run. Resume with capture support to retain future oversized requests; historical payloads were not reconstructed.']


def export_embedded_materials(directory, payload, folder):
    """Extract already captured source content with the same naming and collision rules."""
    resolved_names = source_names(directory, payload)
    materials = []
    exported = {}
    def extract(value, pointer=''):
        if isinstance(value, dict):
            for key in ('content', 'excerpt'):
                if not isinstance(value.get(key), str):
                    continue
                content = value[key].encode('utf-8', errors='surrogatepass')
                relative, resolved = export_source_path(value, resolved_names, len(materials) + 1)
                original = str(value.get('original_identity') or value.get('identity') or value.get('path') or 'embedded')
                relative = Path('sources') / relative
                content_hash = hashlib.sha256(content).hexdigest()
                collision = relative.as_posix().casefold()
                if collision in exported and exported[collision] != content_hash:
                    relative = Path('occurrences') / f'{len(materials) + 1:05d}' / relative
                exported[relative.as_posix().casefold()] = content_hash
                name = relative.as_posix()
                target = folder / relative
                if not target.resolve().is_relative_to(folder.resolve()) or target.is_symlink():
                    raise ValueError('Diagnostic source path must stay inside the capture folder')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                materials.append(dict(file=name, original_identity=original, original_path=resolved,
                                      name_resolution="resolved" if resolved else "unresolved", json_pointer=pointer + '/' + key,
                                      bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
            for key, child in value.items():
                extract(child, pointer + '/' + str(key).replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                extract(child, pointer + '/' + str(index))
    extract(payload)
    manifest = folder / 'materials.json'
    if manifest.is_symlink():
        raise ValueError('Diagnostic file must not be a symbolic link')
    manifest.write_text(json.dumps(dict(materials=materials,
        embedded_occurrences=len(materials), unique_content_hashes=len({item['sha256'] for item in materials})),
        indent=2, ensure_ascii=True), encoding='utf-8')
