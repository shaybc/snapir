"""Read-only input expansion, role separation, and source/JAR fingerprints."""
import codecs
from pathlib import Path
from comparator.models import digest, file_hash


def catalog(request, output, settings):
    """Expand explicit code/dependency paths without scanning output or following symlinks."""
    if not isinstance(request, dict) or request.get('schema_version') != 'java-behavior-comparison-request-v1':
        raise ValueError('Invalid comparison request schema')
    records, jars, files, warnings = [], [], {}, []
    output = Path(output).resolve()
    for side in ('original','generated'):
        item = request.get(side)
        if not isinstance(item, dict): raise ValueError('Missing input side: ' + side)
        encoding = item.get('encoding','UTF-8'); codecs.lookup(encoding)
        if not isinstance(item.get('entry_methods',[]),list) or not all(isinstance(v,str) and v for v in item.get('entry_methods',[])):
            raise ValueError('entry_methods must list method names')
        for role in ('sources','dependency_sources','jars'):
            paths = item.get(role, [])
            if not isinstance(paths, list): raise ValueError(role + ' must list paths')
            if role=='sources' and not paths: raise ValueError(side + ' sources are required')
            for value in paths:
                path = Path(value).absolute()
                if path.is_symlink() or not path.exists(): raise ValueError('Missing or linked input: ' + str(path))
                path = path.resolve()
                if output == path or path.is_dir() and output.is_relative_to(path):
                    raise ValueError('Comparison output must be outside input directories')
                children = sorted(path.rglob('*')) if path.is_dir() else [path]
                for child in children:
                    if child.is_symlink(): raise ValueError('Linked input is not accepted: ' + str(child))
                    if not child.is_file(): continue
                    relative = child.relative_to(path).parts if path.is_dir() else ()
                    if any(part in settings['source_excludes'] for part in relative): continue
                    child = child.resolve(); key = str(child)
                    files[key] = file_hash(child)
                    if role == 'jars':
                        if child.suffix.lower()=='.jar': jars.append(dict(path=key, side=side))
                    elif child.suffix.lower()=='.java':
                        records.append(dict(path=key,side=side,encoding=encoding,target=role=='sources'))
    # The same physical Java file may be supplied as a target and dependency; index it once per side.
    unique = {}
    for item in records:
        key = (item['side'],item['path'])
        if key not in unique or item['target']: unique[key]=item
    targets = request.get('targets', [])
    if not isinstance(targets,list) or any(not isinstance(t,dict) or set(t)!={'original_class','generated_class'}
        or not all(isinstance(v,str) and v for v in t.values()) for t in targets):
        raise ValueError('targets must list original_class/generated_class pairs')
    identity = dict(files=files, targets=targets,
                    encodings={side:request[side].get('encoding','UTF-8') for side in ('original','generated')},
                    entry_methods={side:request[side].get('entry_methods',[]) for side in ('original','generated')})
    return dict(sources=list(unique.values()),jars=jars,files=files,targets=targets,
                input_hash=digest(identity),warnings=warnings)


def unchanged(files):
    """Reject a run whose inspected bytes changed during analysis."""
    return all(Path(path).is_file() and file_hash(path)==revision for path,revision in files.items())
