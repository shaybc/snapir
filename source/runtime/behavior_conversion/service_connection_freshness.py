"""Check accepted resource facts against current loaded channel configuration."""

import json
from pathlib import Path
from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath


def verify_connection_sources(config, profile, connections):
    """Check service/source evidence; external connector values are not conversion inputs."""
    if not connections:
        return
    index = discover_java_sources(config.source_root)
    classpath = discover_conversion_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables, profile=profile)
    for record in connections:
        source = 'getService(' + json.dumps(record['service_id']) + ');'
        current = resolve_service_connections(config.source_root, record['channel'], {'saved-lookup': source}, {}, index, classpath)
        if len(current) != 1:
            raise ValueError('Service evidence changed since acceptance: ' + record['service_id'])
        found = current[0].model_dump()
        # Unit/source fingerprints cover the contract's caller code. This probe only
        # recreates the service lookup, so it cannot reconstruct all caller keys.
        if record.get('configuration_contract') and not found['configuration_contract']:
            raise ValueError('External connection contract changed; refresh the affected operation')
        for key in ('implementation', 'configuration', 'connector_id', 'connector_configuration', 'driver_class', 'driver_candidates', 'supporting_hashes'):
            if found[key] != record[key]:
                raise ValueError('Service/connector evidence changed since acceptance: ' + record['channel'] + '/' + record['service_id'] +
                                 ' (' + key + '); refresh the affected operation, preserving unrelated accepted units')
