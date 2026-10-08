"""Resolve channel configuration inheritance without merging unrelated tag namespaces."""

from tools.component_inventory_tools.xml_documents import read_xml, tag_name
from xml.etree import ElementTree


def channel_for_path(path):
    """Return declared path ownership, not the consumer channel."""
    for index, part in enumerate(path.parts[:-1]):
        if part.lower() == "channel":
            return path.parts[index + 1].upper()
    return None


def load_channel_mappings(workspace):
    """Return effective tag mappings with their original configuration-file provenance."""
    definitions = {}
    diagnostics = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name.lower() != "dse.ini":
            continue
        if not path.resolve().is_relative_to(workspace):
            diagnostics.append("Channel configuration is outside workspace: " + str(path))
            continue
        channel = channel_for_path(path)
        if channel is None:
            diagnostics.append("Channel ownership is unavailable for " + str(path.relative_to(workspace)))
            continue
        definitions.setdefault(channel, []).append(path)
    cache = {}
    scopes = {}

    def resolve(channel, active):
        if channel in cache:
            return cache[channel]
        if channel in active:
            raise ValueError("Channel import cycle: " + channel)
        paths = definitions.get(channel, [])
        if len(paths) != 1:
            raise ValueError("Missing or ambiguous channel configuration: " + channel)
        root = read_xml(paths[0])
        values = {}
        dependencies = {channel}
        for collection in root:
            if collection.get("id") == "import":
                for entry in collection:
                    imported = entry.get("id")
                    if imported:
                        inherited = resolve(imported.upper(), {*active, channel})
                        dependencies.update(scopes.get(imported.upper(), []))
                        for key, value in inherited.items():
                            if key in values and values[key]["fqcn"] != value["fqcn"]:
                                raise ValueError("Conflicting inherited mapping for " + channel + "/" + key)
                            values[key] = value
        local_values = {}
        for settings in root:
            if settings.get("id") != "settings":
                continue
            for tags in settings:
                if tags.get("id") != "tags":
                    continue
                for group in tags:
                    for field in group:
                        name, fqcn = field.get("id"), field.get("value")
                        if tag_name(field) != "field" or not name or not fqcn:
                            continue
                        if name in local_values and local_values[name] != fqcn:
                            raise ValueError("Conflicting local mapping for " + channel + "/" + name)
                        local_values[name] = fqcn
                        values[name] = dict(fqcn=fqcn, source=paths[0].relative_to(workspace).as_posix(),
                                            origin_channel=channel, group=group.get("id"))
        cache[channel] = values
        scopes[channel] = sorted(dependencies)
        return values

    for channel in definitions:
        try:
            resolve(channel, set())
        except (ValueError, OSError, ElementTree.ParseError) as exc:
            diagnostics.append(str(exc))
            cache[channel] = {}
    return cache, diagnostics, scopes
