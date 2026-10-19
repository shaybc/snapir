"""Resolve channel-owned service lookups to configured external resources."""

import hashlib
from pathlib import Path
from xml.etree import ElementTree
from models.service_connection import ServiceConnection
from tools.component_inventory_tools.identity import stable_id
from tools.component_inventory_tools.loaded_service_documents import load_service_documents
from tools.component_inventory_tools.service_definitions import index_service_definitions
from tools.component_inventory_tools.java_service_lookups import service_lookups
from tools.maven_dependency_tools.driver_metadata import driver_candidates


def resolve_service_connections(workspace, channel, sources, parameters, source_index, classpath):
    """Resolve only reachable lookups, recording ambiguity instead of choosing defaults."""
    workspace = Path(workspace).resolve()
    lookups = []
    for name, content in sources.items():
        lookups.extend(dict(item, caller=name) for item in service_lookups(content, parameters))
    if not lookups:
        return []
    try:
        mappings, documents = load_service_documents(workspace, channel)
        services, connectors = index_service_definitions(workspace, channel, mappings, documents)
        registry_issue = None
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        services, connectors, registry_issue = {}, {}, str(exc)
    records = {}
    for lookup in lookups:
        name = lookup['service_name'] or '<dynamic:' + lookup['caller'] + ':' + str(lookup['line']) + '>'
        identity = stable_id(channel, name)
        if identity in records:
            records[identity].conditions.append(lookup['condition'])
            continue
        result = ServiceConnection(connection_id=identity, channel=channel, service_id=name, conditions=[lookup['condition']])
        records[identity] = result
        result.source_evidence.append(dict(caller=lookup['caller'], line=lookup['line'], lookup=name))
        if registry_issue:
            result.issues.append(registry_issue)
            continue
        definitions = services.get(name, [])
        if len(definitions) != 1:
            result.issues.append('Dynamic service lookup needs a configured binding' if not lookup['service_name'] else
                                 'Missing or ambiguous service instance: ' + name + ' in channel ' + channel)
            continue
        definition = definitions[0]
        result.service_tag = definition['tag']
        result.implementation = definition['implementation']
        result.configuration = definition['attributes']
        result.source_evidence.append(definition)
        pending, visited = [result.implementation], set()
        while pending:
            fqcn = pending.pop()
            if fqcn in visited:
                continue
            visited.add(fqcn)
            paths = source_index.classes.get(fqcn, [])
            if len(paths) > 1:
                result.issues.append('Ambiguous service implementation source: ' + fqcn)
            elif paths:
                path = Path(paths[0]).resolve()
                if not path.is_relative_to(workspace):
                    result.issues.append('Service source outside workspace: ' + fqcn)
                    continue
                result.supporting_sources.append(str(path))
                content = path.read_text(encoding='utf-8-sig')
                import re
                parent = re.search(r'\bextends\s+([\w.]+)', content)
                imports = re.findall(r'\bimport\s+([\w.]+)\s*;', content)
                package = re.search(r'\bpackage\s+([\w.]+)', content)
                if parent:
                    candidates = [parent[1], *((package[1] + '.' + parent[1],) if package else ()),
                                  *(value for value in imports if value.rsplit('.', 1)[-1] == parent[1])]
                    pending.extend(value for value in candidates if value in source_index.classes)
                pending.extend(value for value in imports if value in source_index.classes)
            else:
                import constants
                if not any(fqcn.startswith(package + '.') for package in constants.COMPOSER_FRAMEWORK_PACKAGES):
                    result.issues.append('Service implementation source or documented behavior is unavailable: ' + fqcn)
            # Framework classes may be documented replacement boundaries; missing
            # application sources are checked by the existing closure resolver.
        pool = result.configuration.get('poolName')
        if pool:
            candidates = connectors.get(pool, [])
            result.connector_id = pool
            if len(candidates) != 1:
                result.issues.append('Missing or ambiguous connector pool: ' + str(pool))
                continue
            connector = candidates[0]
            attrs = connector['attributes']
            result.connector_configuration = attrs
            if connector.get('manager'):
                result.connector_configuration = dict(attrs, manager=connector['manager'])
            result.source_evidence.append(connector)
            result.database_type = attrs.get('dbType')
            result.driver_class = attrs.get('JDBCDriver')
            result.resource_kind = 'jdbc' if result.driver_class or connector['tag'].startswith('JDBC') else 'external'
            result.ownership = dict(auto_commit=result.configuration.get('autoCommit'),
                                    status='derive acquisition, reuse and release from service and step source')
            if result.resource_kind == 'jdbc' and not result.driver_class:
                result.issues.append('JDBC connector driver class is unavailable: ' + pool)
            elif result.driver_class:
                result.driver_candidates = driver_candidates(result.driver_class, classpath)
                unique = [item['dependency'] for item in result.driver_candidates if item.get('dependency')]
                if len(result.driver_candidates) == 1 and len(unique) == 1:
                    result.driver_dependency = dict(unique[0])
                    # Vendor APIs referenced by application code need compile scope;
                    # a pure configured driver can remain a runtime dependency.
                    from runtime.java_public_type import _code
                    import re
                    imported = {match[1] for content in sources.values() for match in
                        re.finditer(r'\bimport\s+(?:static\s+)?([\w.]+)\s*;', _code(content))}
                    jar_name = result.driver_candidates[0]['jar']
                    required = {name for name in imported if any(location.startswith('jar:') and
                        Path(location[4:]).name == jar_name for location in classpath.classes.get(name, []))}
                    if required:
                        result.driver_dependency['scope'] = 'compile'
                        result.driver_dependency['required_classes'] = sorted(required | {result.driver_class})
                else:
                    result.issues.append('Driver coordinates/version need verification for ' + result.driver_class)
            result.decision_id = stable_id(channel, pool)
            result.decision_fingerprint = stable_id(channel, connector, result.driver_candidates)
        result.fingerprint = stable_id(result.model_dump(exclude={'fingerprint', 'supporting_sources', 'conditions', 'source_evidence'}),
            result.source_evidence[1:],
            [(str(Path(path).relative_to(workspace)), hashlib.sha256(Path(path).read_bytes()).hexdigest()) for path in result.supporting_sources])
    for result in records.values():
        result.supporting_hashes = {str(Path(path).relative_to(workspace)): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                   for path in result.supporting_sources}
        if not result.fingerprint:
            result.fingerprint = stable_id(result.model_dump(exclude={'fingerprint', 'source_evidence', 'conditions'}))
        if not result.decision_id:
            result.decision_id = result.connection_id
            result.decision_fingerprint = result.fingerprint
    return list(records.values())
