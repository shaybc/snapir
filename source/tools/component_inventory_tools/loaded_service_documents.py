"""Read only channel-loaded service documents and namespace-specific tag mappings."""

from pathlib import Path
from tools.component_inventory_tools.channel_mappings import channel_for_path
from tools.component_inventory_tools.xml_documents import read_xml, tag_name


def load_service_documents(workspace, channel):
    """Return effective loaded documents/mappings with provenance and explicit issues."""
    workspace = Path(workspace).resolve()
    registries = {}
    for path in workspace.rglob('*'):
        if path.is_file() and path.name.lower() in {'dse.ini', 'dsc.ini'}:
            owner = channel_for_path(path)
            if owner:
                registries.setdefault(owner, []).append(path)
    cache = {}

    def resolve(name, active):
        if name in active:
            raise ValueError('Channel service import cycle: ' + name)
        if name in cache:
            return cache[name]
        paths = registries.get(name, [])
        if len(paths) != 1:
            raise ValueError('Missing or ambiguous channel service registry: ' + name)
        registry = paths[0]
        if not registry.resolve().is_relative_to(workspace):
            raise ValueError('Channel service registry outside workspace: ' + str(registry))
        root = read_xml(registry)
        mappings, documents = {}, {}
        for collection in root:
            if collection.get('id') == 'import':
                for entry in collection:
                    inherited, loaded = resolve(entry.get('id', '').upper(), {*active, name})
                    for key, value in inherited.items():
                        if key in mappings and mappings[key]['implementation'] != value['implementation']:
                            raise ValueError('Conflicting imported service mapping: ' + name + '/' + str(key))
                        mappings[key] = value
                    documents.update(loaded)
        for settings in root:
            if settings.get('id') != 'settings':
                continue
            for collection in settings:
                if collection.get('id') == 'tags':
                    local = {}
                    for group in collection:
                        for entry in group:
                            if tag_name(entry) != 'field' or not entry.get('id') or not entry.get('value'):
                                continue
                            key = (group.get('id'), entry.get('id'))
                            value = dict(implementation=entry.get('value'), registry=registry.relative_to(workspace).as_posix(),
                                         origin_channel=name)
                            if key in local and local[key]['implementation'] != value['implementation']:
                                raise ValueError('Conflicting local service mapping: ' + name + '/' + str(key))
                            local[key] = value
                    mappings.update(local)
                if collection.get('id') == 'files':
                    for group in collection:
                        if group.get('id') != 'defaultFile':
                            continue
                        for entry in group:
                            value = entry.get('id')
                            if not value:
                                continue
                            path = Path(value)
                            candidates = [path] if path.is_absolute() else [workspace / path, registry.parent / path]
                            # Eclipse project-local references are commonly relative to its source root.
                            if not path.is_absolute():
                                candidates.extend(parent / path for parent in registry.parents if parent.is_relative_to(workspace))
                            found = {candidate.resolve() for candidate in candidates if candidate.is_file()}
                            if len(found) != 1:
                                raise ValueError('Missing or ambiguous loaded service document: ' + value)
                            target = found.pop()
                            if not target.is_relative_to(workspace):
                                raise ValueError('Loaded service document outside workspace: ' + value)
                            documents[str(target)] = dict(path=target, channel=name, root=read_xml(target))
        # Local instance IDs override imported instances; source channel is retained.
        result = mappings, documents
        cache[name] = result
        return result

    return resolve(channel.upper(), set())
