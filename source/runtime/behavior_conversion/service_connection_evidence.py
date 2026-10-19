"""Attach discovered connection facts to a whole configured conversion unit."""

from pathlib import Path
from xml.etree import ElementTree
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.component_inventory_tools.service_connections import resolve_service_connections
from tools.state_store_tools.service_connections import remember, decision
from tools.component_inventory_tools.identity import stable_id

SERVICE_CONNECTION_INSTRUCTION = '''The service_connections evidence identifies the existing
external systems used by this configured unit. Preserve its channel-specific service and
connector identities, selected database technology, driver class and verified dependency
coordinates/version/scope. Do not introduce another vendor or invent connection defaults.
Replace Composer getService/context lookups with explicit native providers, while preserving
conditional selection, timeout, transaction scope, connection reuse and release behavior from
the supplied service/helper source. Different pools are different resources even if their Java
types match. Do not embed credentials, URLs or canned external replies. Deployment values are
supplied separately. Unresolved facts must be reported, never filled by plausible guesses.'''


def connection_evidence(conn, config, channel, unit_key, sources, xml, profile=None):
    """Resolve and persist source-backed records, reusing decisions only for matching facts."""
    index = discover_java_sources(config.source_root)
    classpath = discover_java_classpath(config.source_root, getattr(profile, 'classpath_jars', []),
                                        getattr(profile, 'eclipse_classpath_variables', {}))
    parameters = ElementTree.fromstring(xml).attrib
    records = resolve_service_connections(config.source_root, channel, sources, parameters, index, classpath)
    for record in records:
        answer = decision(conn, config.run_id, record.decision_id, record.decision_fingerprint)
        if answer and answer.get('driver_dependency') and record.driver_class:
            record.driver_dependency = answer['driver_dependency']
            record.issues = [issue for issue in record.issues if not issue.startswith('Driver coordinates/version')]
        if answer and answer.get('transaction_scope'):
            record.ownership['user_confirmed_transaction_scope'] = answer['transaction_scope']
        if answer and answer.get('service_alias'):
            alternatives = dict(parameters)
            # Explicit aliases are confirmed decisions, never automatic case folding.
            renamed = dict(sources)
            if answer.get('service_alias'):
                renamed = {key: value.replace('"' + record.service_id + '"', '"' + answer['service_alias'] + '"') for key, value in sources.items()}
            resolved = resolve_service_connections(config.source_root, channel, renamed, alternatives, index, classpath)
            replacement = next((item for item in resolved if item.service_id == answer.get('service_alias', record.service_id)), None)
            if replacement:
                replacement.connection_id = record.connection_id
                replacement.fingerprint = stable_id(record.fingerprint, replacement.fingerprint)
                replacement.source_evidence.append(dict(user_confirmed_alias=answer['service_alias'], original_service_id=record.service_id))
                records[records.index(record)] = replacement
    for record in records:
        # Alias resolution may uncover a shared pool whose separate driver question
        # was answered on an earlier Resume.
        answer = decision(conn, config.run_id, record.decision_id, record.decision_fingerprint)
        if answer and answer.get('driver_dependency') and record.driver_class:
            record.driver_dependency = answer['driver_dependency']
            record.issues = [issue for issue in record.issues if not issue.startswith('Driver coordinates/version')]
    consumer = channel + '/' + unit_key.split('/', 1)[0]
    remember(conn, config.run_id, consumer, unit_key, records)
    return records, index, classpath


def attach_unit_connections(conn, config, closure, unit, profile=None):
    """Enrich only affected units; empty discovery does not change old unit identities."""
    if not any('getService' in source.content for source in unit.sources):
        return unit
    records, _, _ = connection_evidence(conn, config, closure['channel'], closure['operation_id'] + '/' + unit.logical_id,
        {source.identity: source.content for source in unit.sources}, unit.configuration_xml, profile)
    from models.behavior_unit import SourceEvidence
    sources = {source.identity: source for source in unit.sources}
    for record in records:
        for name in record.supporting_sources:
            path = Path(name)
            key = path.relative_to(Path(config.source_root).resolve()).as_posix()
            import hashlib
            sources.setdefault(key, SourceEvidence(identity=key, content=path.read_text(encoding='utf-8-sig'),
                content_hash=hashlib.sha256(path.read_bytes()).hexdigest()))
    data = [record.model_dump(mode='json', exclude={'supporting_sources'}) for record in records]
    if not data:
        return unit
    return unit.model_copy(update=dict(service_connections=data, sources=list(sources.values()),
        fingerprint=stable_id(unit.fingerprint, [(record.fingerprint, record.driver_dependency) for record in records]),
        unit_id=unit.kind + '-' + stable_id(unit.fingerprint, [(record.fingerprint, record.driver_dependency) for record in records])[:24]))
