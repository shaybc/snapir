"""Discover component candidates and collect their original source dependency closure."""
from pathlib import Path
from xml.etree import ElementTree

from tools.source_discovery_tools import discover_java_sources, resolve_indexed_source
from tools.java_analysis_tools.source_dependencies.parser import iter_source_references
from tools.java_analysis_tools.source_dependencies.resolution import resolve_reference
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def source_catalog(root):
    """Use canonical source discovery and the shared JDK syntax parser, never AI naming guesses."""
    index = discover_java_sources(root)
    if index.issues:
        raise ValueError('Component source discovery: ' + '; '.join(index.issues))
    documents = {}
    for node in iter_source_references([path for paths in index.classes.values() for path in paths], strip_bom=True):
        if node.tag == 'issue':
            raise ValueError('Component source analysis: ' + node.get('message', 'invalid Java'))
        documents[str(Path(node.get('path')).resolve())] = ElementTree.fromstring(ElementTree.tostring(node))
    return index, documents


def component_catalog(root, *, catalog=None, profile=None, classpath=None, include_formats=True):
    """List inherited syntax candidates; exact public entry contracts are checked before generation."""
    index, documents = catalog or source_catalog(root)
    metadata = {name: [documents[path].find('java_class') for path in paths] for name, paths in index.classes.items()}
    from tools.conversion_tools.format_candidates import format_candidates
    result = dict(format=format_candidates(root, (index, documents), profile, classpath) if include_formats else [], op_step=[])
    for name in sorted(metadata):
        methods, parents, pending, seen = set(), set(), [name], set()
        while pending:
            owner = pending.pop()
            if owner in seen:
                continue
            seen.add(owner)
            for declaration in metadata.get(owner, []):
                if declaration is None:
                    continue
                methods.update(item.get('name') for item in declaration.findall('method'))
                parent = declaration.get('parent')
                ancestors = ([parent] if parent else []) + [item.get('name') for item in declaration.findall('interface')]
                for ancestor in ancestors:
                    parents.add(ancestor)
                    pending.append(ancestor)
                    if ancestor not in metadata:
                        # Documentary names may omit wildcard-import resolution. Use the shared resolver.
                        for path in index.classes.get(owner, []):
                            document = documents[path]
                            for reference in document.findall('reference'):
                                if reference.get('kind') != 'type' or reference.get('name').rsplit('.', 1)[-1] != ancestor.rsplit('.', 1)[-1]:
                                    continue
                                targets, issue = resolve_reference(reference, document, index, path)
                                for target in targets:
                                    resolved = documents[target].find('java_class')
                                    if resolved is not None:
                                        pending.append(resolved.get('fqcn'))
        if {'execute', 'CCExecute', 'ccExecute'}.intersection(methods) or any(
                parent.startswith('com.ibm.') and parent.rsplit('.', 1)[-1] in {'OperationStep', 'CCOperationStep'} for parent in parents):
            result['op_step'].append(name)
    return result


def component_sources(profile, catalog, names=None):
    """Resolve all supplied Java dependencies using existing project visibility and ambiguity checks."""
    index, documents = catalog
    paths = {}
    pending = [resolve_indexed_source(index, name, profile.scoped_java_project) for name in names or profile.selected_components]
    if any(path is None for path in pending):
        raise ValueError('Selected component source is unavailable')
    while pending:
        path = pending.pop()
        if path in paths:
            continue
        document = documents[path]
        paths[path] = document
        for reference in document.findall('reference'):
            targets, issue = resolve_reference(reference, document, index, path)
            if issue and targets:
                raise ValueError('Component dependency is ambiguous: ' + issue)
            pending.extend(target for target in targets if target not in paths)
    sources, origins = [], []
    names = {path: name for name, values in index.classes.items() for path in values}
    for path in sorted(paths):
        # Read exact text/hash together; source verification repeats before every model call.
        raw = Path(path).read_bytes()
        import hashlib
        revision = hashlib.sha256(raw).hexdigest()
        identity = 'source-' + digest([names[path], index.class_projects[path]])
        sources.append(dict(identity=identity, content=raw.decode('utf-8'), content_hash=revision))
        origins.append(dict(definition_id=identity, fqcn=names[path], source_file=path, source_hash=revision,
                            source_project=index.class_projects[path], status='verified_source'))
    return sources, origins


def verify_sources(origins):
    """Reject changed, missing, or substituted original files before scoped generation or reuse."""
    for origin in origins:
        if file_digest(Path(origin['source_file'])) != origin['source_hash']:
            raise ValueError('Standalone component source changed: ' + origin['fqcn'])
