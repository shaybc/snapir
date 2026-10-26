"""Retain existing resource ownership rules within verified scoped source boundaries."""

from pathlib import Path

from runtime.behavior_conversion.service_connection_evidence import connection_evidence
from tools.component_inventory_tools.identity import stable_id
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.source_discovery_tools import discover_java_sources
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project


def attach_scoped_connections(conn, config, closure, unit, profile, classpath_index=None):
    """Reuse connection decisions without admitting unchecked supporting Java sources."""
    if unit.operation_calls or not any('getService' in source.content for source in unit.sources):
        return unit
    project = scoped_source_project(profile, closure.channel)
    index = discover_java_sources(config.source_root)
    if project not in index.source_roots:
        raise ValueError('Service connection evidence requires the explicit scoped source project')
    allowed, pending = set(), [project]
    while pending:
        current = pending.pop()
        if current in allowed:
            continue
        allowed.add(current)
        pending.extend(index.project_references.get(current, []))
    index = index.model_copy(update={'classes': {name: [path for path in paths if index.class_projects[path] in allowed]
        for name, paths in index.classes.items() if any(index.class_projects[path] in allowed for path in paths)}})
    classpath = classpath_index if classpath_index is not None else discover_java_classpath(
        config.source_root, getattr(profile, 'classpath_jars', []), getattr(profile, 'eclipse_classpath_variables', {}))
    # Native operation calls replace this dispatch boundary; it is not an external
    # service resource. Keep the original source in the unit's conversion evidence.
    dispatchers = {origin['definition_id'] for origin in closure.java_origins
        if getattr(closure, 'calls', ()) and origin.get('fqcn') == 'com.ibm.il.dse.cc.cut.CCComplexOpStep'
        and origin.get('status') == 'verified_source'}
    records, _, _ = connection_evidence(conn, config, closure.channel,
        closure.operation_id + '/' + unit.occurrence_id,
        {source.identity: source.content for source in unit.sources if source.identity not in dispatchers},
        unit.configuration_xml, profile, source_index=index, classpath_index=classpath, persist=False)
    verified = {str(Path(origin['source_file']).resolve()): origin for origin in closure.java_origins
                if origin['status'] == 'verified_source'}
    for record in records:
        if record.issues:
            raise ValueError('Service connection requires explicit resolution: ' + '; '.join(record.issues))
        for filename in record.supporting_sources:
            origin = verified.get(str(Path(filename).resolve()))
            if origin is None:
                raise ValueError('Service supporting source is outside the checked scoped closure: ' + filename)
            read_java_source(filename, expected_hash=origin['source_hash'])
    data = [record.model_dump(mode='json', exclude={'supporting_sources'}) for record in records]
    if not data:
        return unit
    digest = stable_id(unit.fingerprint, data)
    return unit.model_copy(update=dict(service_connections=data, fingerprint=digest, unit_id='scoped-unit-' + digest))
