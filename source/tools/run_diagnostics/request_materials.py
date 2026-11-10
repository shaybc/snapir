"""Export saved oversized request materials without reading original workspace sources."""

import hashlib
import json
from pathlib import Path
import re


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
        materials = []
        def extract(value, pointer=''):
            if isinstance(value, dict):
                for key in ('content', 'excerpt'):
                    if not isinstance(value.get(key), str):
                        continue
                    content = value[key].encode('utf-8', errors='surrogatepass')
                    original = str(value.get('path') or value.get('original_identity') or value.get('identity') or 'embedded.txt')
                    basename = re.sub(r'[^A-Za-z0-9._-]', '_', original.replace('\\', '/').rsplit('/', 1)[-1])[:120] or 'embedded.txt'
                    name = f'{len(materials) + 1:05d}-' + basename
                    target = folder / name
                    if target.is_symlink():
                        raise ValueError('Diagnostic file must not be a symbolic link')
                    target.write_bytes(content)
                    materials.append(dict(file=name, original_identity=original, json_pointer=pointer + '/' + key,
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
        count += 1
    if count:
        return [f'Oversized request captures exported: {count}', 'Request materials folder: ' + str(destination),
                'Each capture includes request.json, instructions.txt, metadata.json, extracted text, and materials.json.',
                'Budget-check captures were intended requests, not sent model calls. Repeated content remains visible in the manifest.']
    return ['No exact oversized request captures are available for this run. Resume with capture support to retain future oversized requests; historical payloads were not reconstructed.']
