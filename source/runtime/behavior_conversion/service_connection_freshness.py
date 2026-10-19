"""Check accepted resource facts against current loaded channel configuration."""

import json
from pathlib import Path
from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath


def verify_connection_sources(config, profile, connections):
    """Reject changed connector mappings/driver files without exposing credentials."""
    if not connections:
        return
    index = discover_java_sources(config.source_root)
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    for record in connections:
        source = 'getService(' + json.dumps(record['service_id']) + ');'
        current = resolve_service_connections(config.source_root, record['channel'], {'saved-lookup': source}, {}, index, classpath)
        if len(current) != 1:
            raise ValueError('Service evidence changed since acceptance: ' + record['service_id'])
        found = current[0].model_dump()
        for key in ('implementation', 'configuration', 'connector_id', 'connector_configuration', 'driver_class', 'driver_candidates', 'supporting_hashes'):
            if found[key] != record[key]:
                raise ValueError('Service/connector evidence changed since acceptance: ' + record['channel'] + '/' + record['service_id'] +
                                 ' (' + key + '); refresh the affected operation, preserving unrelated accepted units')
