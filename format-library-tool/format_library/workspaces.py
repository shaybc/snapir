"""Prepare immutable component input folders and human-readable launchers."""
import re
import shutil
from pathlib import Path
from format_library.configuration import TOOL_ROOT
from format_library.files import digest, file_hash, inside, read_json, write_json


def api_revision():
    """Fingerprint the exact common API source files copied into every conversion."""
    return digest({path.relative_to(TOOL_ROOT / 'common-api').as_posix(): file_hash(path)
                   for path in sorted((TOOL_ROOT / 'common-api/src').rglob('*.java'))})


def folder_name(group):
    """Retain recognizable class names while disambiguating packages and conversion cycles."""
    label = '+'.join(name.rsplit('.', 1)[-1] for name in group['members'])
    return re.sub(r'[^A-Za-z0-9_.+-]', '_', label)[:100] + '--' + group['id'][6:14]


def prepare(config, plan, names=()):
    """Copy complete original closures and required JARs; never overwrite an existing folder."""
    from format_library.planning import select_groups
    from format_library.prompts import write_prompt
    root = Path(config['output_root'])
    for path in (str(TOOL_ROOT / 'run.cmd'), config['_config_path']):
        if any(character in path for character in ('%', '"', '\r', '\n')):
            raise ValueError('CMD launcher paths cannot contain percent signs, quotes or newlines')
    write_json(root / 'plan.json', plan)
    created = []
    for group in select_groups(plan, names):
        preparation_hash = digest([plan['discovery_hash'], group, api_revision(), config['native_package'],
                                   config['target_java_version'], config['known_dependencies']])
        folder = root / 'components' / folder_name(group)
        if folder.exists():
            existing = read_json(folder / 'component.json')
            if existing.get('preparation_hash') != preparation_hash:
                raise ValueError('Prepared folder has different evidence. Use a new output_root: ' + str(folder))
            created.append(folder)
            continue
        folder.mkdir(parents=True)
        manifest = dict(schema_version='format-library-component-v1', **group,
            api_version=1, api_hash=api_revision(), native_package=config['native_package'],
            target_java_version=config['target_java_version'], known_dependencies=config['known_dependencies'],
            original_classes={name: plan['classes'][name] for name in group['source_classes']},
            native_classes={name: config['native_package'] + '.c' + group['id'][6:14] + '.Native' + name.rsplit('.', 1)[-1]
                            for name in group['members']}, files=[], binaries=[],
            preparation_hash=preparation_hash)
        source_files = sorted({plan['classes'][name]['file'] for name in group['source_classes']})
        projects = {plan['classes'][name]['project'] for name in group['source_classes']}
        libraries = sorted({path for item in plan['projects'] if item['id'] in projects for path in item['libraries']})
        for kind, paths in [('sources', source_files), ('jars', libraries)]:
            for original in paths:
                path = Path(original)
                if not path.is_file():
                    manifest['blockers'].append('Missing required input: ' + original)
                    continue
                revision = file_hash(path)
                if plan['hashes'].get(original) != revision:
                    raise ValueError('Input changed since discovery: ' + original)
                relative = kind + '/' + digest(original)[:12] + '/' + path.name
                destination = inside(folder, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                item = dict(path=relative, original=original, sha256=revision)
                manifest['files' if kind == 'sources' else 'binaries'].append(item)
        shutil.copytree(TOOL_ROOT / 'common-api/src', folder / 'common-api/src')
        manifest['manifest_hash'] = digest(manifest)
        for name in ('generated', 'prerequisites', 'attempts'):
            (folder / name).mkdir()
        write_json(folder / 'component.json', manifest)
        # No credentials are embedded. Both config and Python selection remain external.
        launcher = ('@echo off\r\nsetlocal\r\n'
                    'call "%~dp0..\\..\\..\\run.cmd" --config "' + config['_config_path'] +
                    '" convert --folder "%~dp0."\r\nset "conversion_exit=%ERRORLEVEL%"\r\npause\r\nexit /b %conversion_exit%\r\n')
        # The tool may live elsewhere than output_root; resolve its launcher explicitly.
        launcher = launcher.replace('%~dp0..\\..\\..\\run.cmd', str(TOOL_ROOT / 'run.cmd'))
        (folder / 'convert.cmd').write_bytes(launcher.encode('utf-8'))
        write_prompt(folder, manifest)
        created.append(folder)
    return created


def verify_inputs(folder, manifest):
    """Reject modified original evidence or common API before sending a request."""
    if manifest.get('manifest_hash') != digest({key: value for key, value in manifest.items() if key != 'manifest_hash'}):
        raise ValueError('Prepared component record changed; prepare a new folder')
    for item in manifest['files'] + manifest['binaries']:
        if file_hash(inside(folder, item['path'])) != item['sha256']:
            raise ValueError('Prepared evidence changed: ' + item['path'])
    local = {path.relative_to(folder / 'common-api').as_posix(): file_hash(path)
             for path in sorted((folder / 'common-api/src').rglob('*.java'))}
    if digest(local) != manifest['api_hash']:
        raise ValueError('Prepared common API changed; prepare a new folder')
