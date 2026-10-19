"""Extend checked source closure through named service implementations."""

from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.component_inventory_tools.xml_documents import read_xml


def include_service_sources(workspace, channel, uses, implementations, outgoing, source_index, classpath, add):
    """Collect configured services and inherited helpers without requiring framework source."""
    from pathlib import Path
    from xml.etree import ElementTree
    for use in uses:
        pending = [use['implementation_id']] if use.get('implementation_id') else []
        visited, sources = set(), {}
        while pending:
            key = pending.pop()
            if key in visited or key not in implementations:
                continue
            visited.add(key)
            item = implementations[key]
            path = Path(workspace) / item['source_path']
            if path.is_file():
                sources[item['package_name'] + '.' + item['class_name']] = path.read_text(encoding='utf-8-sig')
            pending.extend(outgoing.get(key, []))
        if not any('getService' in source for source in sources.values()):
            continue
        parameters = ElementTree.fromstring(use['configuration_xml']).attrib
        records = resolve_service_connections(workspace, channel, sources, parameters, source_index, classpath)
        for record in records:
            for source in record.supporting_sources:
                names = [fqcn for fqcn, paths in source_index.classes.items() if source in paths]
                for fqcn in names:
                    add('ibm_java', fqcn, source, origin='Configured service ' + record.service_id)
