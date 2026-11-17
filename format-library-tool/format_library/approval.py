"""Explicit human publication and revision-bound prerequisite material."""
import shutil
import tempfile
from pathlib import Path
from format_library.files import digest, file_hash, inside, read_json, write_json


def _index(root):
    return read_json(root / 'index.json') if (root / 'index.json').is_file() else {}


def _artifact(root, identity, revision):
    """Read an immutable approval and verify its file bytes."""
    folder = inside(root, identity + '/' + revision)
    record = read_json(folder / 'approval.json')
    if record['id'] != identity or record['revision'] != revision:
        raise ValueError('Approved component identity mismatch')
    if digest({key: value for key, value in record.items() if key != 'revision'}) != revision:
        raise ValueError('Approved component record changed')
    for item in record['files']:
        if file_hash(inside(folder, item['path'])) != item['sha256']:
            raise ValueError('Approved component file changed: ' + item['path'])
    common_api = inside(root, 'common-api/' + record['api_hash'])
    api_files = {str(path.relative_to(common_api)).replace('\\', '/'): file_hash(path)
                 for path in sorted((common_api / 'src').rglob('*.java'))}
    if digest(api_files) != record['api_hash']:
        raise ValueError('Approved common API changed')
    return folder, record


def collect_prerequisites(config, folder, manifest, *, copy_files=True):
    """Attach only approved, unmodified components with matching original-source and API revisions."""
    root = Path(config['approved_library_root'])
    index = _index(root)
    original_hashes = {item['original']: item['sha256'] for item in manifest['files']}
    expected = {name: original_hashes[item['file']] for name, item in manifest['original_classes'].items() if item.get('file') in original_hashes}
    result, native_files = [], {}
    for identity in manifest['dependencies']:
        revision = index.get(identity)
        if not revision:
            raise ValueError('Prerequisite needs human approval: ' + identity)
        source, record = _artifact(root, identity, revision)
        if record.get('policy') != manifest.get('policy') or record.get('stage') != manifest['dependency_stages'][identity]:
            raise ValueError('Prerequisite lacks the current foundation policy/stage; prepare and approve it again: ' + identity)
        if set(record.get('members', [])) != set(manifest['dependency_members'][identity]):
            raise ValueError('Prerequisite ownership differs from this preparation: ' + identity)
        if record['api_hash'] != manifest['api_hash']:
            raise ValueError('Prerequisite uses a different common API: ' + identity)
        for name, value in record['original_revisions'].items():
            if expected.get(name) != value:
                raise ValueError('Prerequisite source revision differs: ' + name)
        for dependency in record['prerequisites']:
            if index.get(dependency['id']) != dependency['revision']:
                raise ValueError('Prerequisite was approved against an older dependency: ' + identity)
            _artifact(root, dependency['id'], dependency['revision'])
        for item in record['files']:
            if item['path'].endswith('.java'):
                previous = native_files.setdefault(item['path'], item['sha256'])
                if previous != item['sha256']:
                    raise ValueError('Approved prerequisites contain conflicting native Java: ' + item['path'])
            target = inside(folder, 'prerequisites/' + identity + '/' + revision + '/' + item['path'])
            if target.exists() and file_hash(target) != item['sha256']:
                raise ValueError('Local prerequisite copy was edited: ' + str(target))
            if copy_files and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(inside(source, item['path']), target)
        result.append(dict(id=identity, revision=revision, stage=record['stage'], policy=record['policy'],
            members=record['members'], components=record['components'], files=record['files'],
            original_revisions=record['original_revisions']))
    return result


def approve(config, folder, *, reviewed=False):
    """Serialize shared-index publication and exclude simultaneous candidate generation."""
    from format_library.locking import exclusive
    folder = Path(folder).resolve()
    if not (folder / 'component.json').is_file():
        raise ValueError('Select a prepared component folder')
    with exclusive(Path(config['approved_library_root']) / '.approval.lock'), exclusive(folder / '.conversion.lock'):
        return _approve(config, folder, reviewed=reviewed)


def _approve(config, folder, *, reviewed=False):
    """Publish a human-reviewed candidate; never claim compilation or behavioral verification."""
    if not reviewed:
        raise ValueError('Review generated code first, then pass --reviewed to publish it')
    from format_library.workspaces import verify_inputs
    from format_library.generated_files import production_path
    folder = Path(folder).resolve()
    manifest = read_json(folder / 'component.json')
    verify_inputs(folder, manifest)
    from format_library.foundation_planning import verify_selection
    verify_selection(config, manifest)
    candidate_folder = inside(folder, read_json(folder / 'latest.json')['candidate'])
    candidate = read_json(candidate_folder / 'candidate.json')
    if candidate['preparation_hash'] != manifest['preparation_hash'] or candidate['api_hash'] != manifest['api_hash'] or candidate.get('policy') != manifest['policy'] or candidate.get('stage') != manifest['stage']:
        raise ValueError('Candidate does not match this preparation')
    if candidate.get('group_id') != manifest['id']:
        raise ValueError('Reviewed candidate changed its group identity')
    if manifest['stage'] == 'foundation':
        from format_library.foundation_contracts import exports
        exports(manifest, candidate['components'])
    elif {
            item['original_class']: item['native_class'] for item in candidate['components']} != manifest['native_classes']:
        raise ValueError('Reviewed candidate changed its assigned exported identities')
    current = collect_prerequisites(config, folder, manifest)
    if [(item['id'], item['revision']) for item in current] != [
            (item['id'], item['revision']) for item in candidate['prerequisites']]:
        raise ValueError('Prerequisite approvals changed since generation; regenerate before approving')
    files = []
    # Include reviewed human edits, recording the actual approved bytes. Do not use old generation hashes.
    for path in sorted(candidate_folder.rglob('*')):
        if path.is_symlink():
            raise ValueError('Candidate symlinks are not allowed')
        if not path.is_file() or path.name == 'candidate.json' and path.parent == candidate_folder:
            continue
        relative = str(path.relative_to(candidate_folder)).replace('\\', '/')
        production_path(relative)
        files.append(dict(path=relative, sha256=file_hash(path)))
    if not files:
        raise ValueError('Candidate contains no production files')
    expected = {item['path'] for item in candidate['files']}
    if not expected <= {item['path'] for item in files}:
        raise ValueError('An exported candidate file was removed')
    frozen_files = {item['path'] for prerequisite in current for item in prerequisite['files'] if item['path'].endswith('.java')}
    if frozen_files.intersection(item['path'] for item in files):
        raise ValueError('Reviewed candidate must not replace approved prerequisite Java')
    original_hashes = {item['original']: item['sha256'] for item in manifest['files']}
    record = dict(schema_version='format-library-approval-v2', policy=manifest['policy'], stage=manifest['stage'],
        members=manifest['members'], id=manifest['id'], api_hash=manifest['api_hash'],
        api_version=1, components=candidate['components'], files=files, approval='human_reviewed',
        verified=False, prerequisites=[dict(id=item['id'], revision=item['revision']) for item in current],
        original_revisions={name: original_hashes[item['file']] for name, item in manifest['original_classes'].items()},
        candidate_request_hash=candidate['request_hash'], dependencies=candidate['dependencies'])
    revision = digest(record)
    record['revision'] = revision
    root = Path(config['approved_library_root'])
    api_folder = inside(root, 'common-api/' + manifest['api_hash'])
    for path in sorted((folder / 'common-api/src').rglob('*.java')):
        target = inside(api_folder, str(path.relative_to(folder / 'common-api')).replace('\\', '/'))
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and file_hash(target) != file_hash(path):
            raise ValueError('Shared common API was modified')
        if not target.exists():
            shutil.copyfile(path, target)
    destination = inside(root, manifest['id'] + '/' + revision)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix='approval-', dir=destination.parent) as temporary:
            staging = Path(temporary) / 'artifact'; staging.mkdir()
            for item in files:
                target = inside(staging, item['path'])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(inside(candidate_folder, item['path']), target)
                if file_hash(target) != item['sha256']:
                    raise ValueError('Candidate changed during approval')
            write_json(staging / 'approval.json', record)
            staging.rename(destination)
    _artifact(root, manifest['id'], revision)
    index = _index(root)
    index[manifest['id']] = revision
    write_json(root / 'index.json', index)
    return destination
