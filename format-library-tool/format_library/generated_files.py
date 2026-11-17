"""Validate response structure and publish production-only candidates without executing them."""
import json
import shutil
from pathlib import Path
from format_library.files import digest, file_hash, inside, write_json


def production_path(path):
    """Allow only native production sources/resources or a Maven descriptor."""
    if not isinstance(path, str) or any(part in {'.', '..', ''} for part in path.split('/')):
        raise ValueError('Invalid generated path')
    if path == 'pom.xml':
        return path
    if path.startswith('src/main/java/') and path.endswith('.java'):
        return path
    if path.startswith('src/main/resources/') and Path(path).suffix.lower() not in {'.cmd', '.bat', '.ps1', '.exe', '.sh', '.class', '.jar'}:
        return path
    raise ValueError('Only production code/resources are permitted: ' + path)


def extract(folder, manifest, response, request, attempt, *, config=None):
    """Validate the complete response before writing; retain prior candidates and human edits."""
    payload = json.loads(response)
    if not isinstance(payload, dict):
        raise ValueError('AI response must be an object')
    if payload.get('status') == 'blocked':
        reasons = payload.get('reasons')
        if not isinstance(reasons, list) or not reasons or not all(isinstance(value, str) for value in reasons):
            raise ValueError('Blocked response must explain its missing evidence')
        write_json(attempt / 'result.json', payload)
        return None
    if payload.get('status') != 'generated':
        raise ValueError('AI response status must be generated or blocked')
    components = payload.get('components', [])
    if not isinstance(components, list) or len(components) != len(manifest['members']):
        raise ValueError('Response must declare every target exactly once')
    if not all(isinstance(item, dict) for item in components) or {item.get('original_class') for item in components} != set(manifest['members']):
        raise ValueError('Response target identities differ from the prepared group')
    for item in components:
        if item.get('native_class') != manifest['native_classes'][item['original_class']]:
            raise ValueError('Response changed the assigned native class')
        if not isinstance(item.get('constructors'), list) or not item['constructors'] or not all(isinstance(value, str) for value in item['constructors']):
            raise ValueError('Response must state actual constructor declarations')
    files = payload.get('files', [])
    if not isinstance(files, list) or not files:
        raise ValueError('No production files returned')
    seen = set()
    package_root = manifest['native_package'].replace('.', '/')
    for item in files:
        if not isinstance(item, dict):
            raise ValueError('Every generated file must be an object')
        path = production_path(item['path'])
        inside(attempt, path)
        if path in seen or not isinstance(item.get('content'), str) or not item['content'].strip():
            raise ValueError('Duplicate or empty generated file: ' + path)
        seen.add(path)
        if path.endswith('.java'):
            if not path.startswith('src/main/java/' + package_root + '/'):
                raise ValueError('Generated Java must use the assigned native package')
    for native in manifest['native_classes'].values():
        if 'src/main/java/' + native.replace('.', '/') + '.java' not in seen:
            raise ValueError('Missing exported native class file: ' + native)
    dependencies = payload.get('dependencies', [])
    if not isinstance(dependencies, list) or any(value not in manifest['known_dependencies'] for value in dependencies):
        raise ValueError('Response requested an unapproved dependency; add it to known_dependencies and prepare again')
    # Every successful attempt has its own output, so a retry never destroys reviewed code.
    destination = folder / 'generated' / attempt.name
    if destination.exists():
        raise ValueError('Candidate destination already exists')
    staged = attempt / 'candidate'
    if staged.exists():
        raise ValueError('Staged candidate already exists')
    for item in files:
        path = inside(staged, item['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'], encoding='utf-8')
    from format_library.validator_client import validate
    report = validate(config, staged, attempt)
    shutil.copytree(staged, destination)
    candidate = dict(schema_version='format-library-candidate-v1', status='generated', group_id=manifest['id'],
        api_hash=manifest['api_hash'], preparation_hash=manifest['preparation_hash'], components=components,
        dependencies=dependencies, prerequisites=request['prerequisites'], request_hash=digest(request),
        files=[dict(path=item['path'], sha256=file_hash(inside(destination, item['path']))) for item in files],
        notes=payload.get('notes', []), verified=False,
        validation=dict(status=report['status'], policy_hash=report['policy_hash'], input_hash=report['input_hash'],
                        report=str((attempt / 'validation.json').relative_to(folder))))
    write_json(destination / 'candidate.json', candidate)
    write_json(folder / 'latest.json', dict(candidate=str(destination.relative_to(folder)).replace('\\', '/')))
    return destination
