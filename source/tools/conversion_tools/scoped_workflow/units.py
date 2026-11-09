"""Build independent configured units while reusing verified canonical source excerpts."""

import hashlib
import json
from xml.etree import ElementTree

from models.behavior_unit import SourceEvidence as UnitSource
from models.scoped_configured_unit import ScopedConfiguredUnit
from models.scoped_operation_closure import ScopedOperationClosure
from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
from tools.conversion_tools.scoped_workflow.unit_evidence import format_evidence, java_evidence


def build_scoped_units(conn, config, closure, *, calls=(), source_cache=None, profile=None, classpath_index=None):
    """Return occurrence/role bindings; this creates inputs, never accepted native code."""
    closure = ScopedOperationClosure.model_validate(closure)
    if closure.run_id != config.run_id or closure.status != 'evidence_ready':
        raise ValueError('Scoped units require current evidence-ready qualified closure')
    access = ScopedVaultAccess(conn, config.run_id)
    context = access.operation(closure.channel, closure.operation_id)
    if context.operation_identity != closure.operation_identity or context.definition_id != closure.definition_id:
        raise ValueError('Scoped unit context disagrees with imported identity')
    if {call['step_note'] for call in closure.calls} != {call['note'] for call in calls}:
        raise ValueError('Scoped operation calls require occurrence-bound service contracts')
    sources, cache = SourceEvidence(config.source_root), source_cache if source_cache is not None else {}
    mappings = dict((name, fqcn) for name, fqcn, _ in parse_channel_note(
        access.channel_evidence(context)['markdown'], context.channel))
    units, bindings = [], {}
    from tools.conversion_tools.scoped_reuse.fingerprints import POLICY_VERSION, conversion_policy
    policy = conversion_policy(profile)

    def make(kind, label, occurrence, definition, xml, configuration, attached_calls, roots, definitions):
        origins, external = java_evidence(closure, roots)
        implementations = []
        for origin in origins:
            if origin['status'] != 'verified_source':
                continue
            identity = (origin['definition_id'], origin['source_hash'])
            # Check current bytes even when another unit has cached this source.
            content = read_java_source(origin['source_file'], expected_hash=origin['source_hash'], preserve_line_endings=True)
            if identity not in cache or cache[identity].content != content:
                cache[identity] = UnitSource(identity=identity[0], content=content, content_hash=identity[1])
            implementations.append(cache[identity])
        facts = dict(policy_version=POLICY_VERSION, conversion_policy=policy,
            operation_identity=closure.operation_identity, occurrence_id=occurrence,
            source_definition_id=definition, kind=kind, configuration=configuration,
            closure_evidence_hash=closure.evidence_hash, calls=list(attached_calls),
            java_origins=origins, external_dependencies=external, referenced_definitions=definitions)
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
        unit = ScopedConfiguredUnit(unit_id='scoped-unit-' + digest, kind=kind, logical_id=label,
            operation_identity=closure.operation_identity, occurrence_id=occurrence, source_definition_id=definition,
            effective_configuration=configuration,
            configuration_xml=xml, sources=implementations, consumers=[closure.channel + '/' + closure.operation_id],
            referenced_definitions=definitions, external_dependencies=external,
            operation_calls=list(attached_calls), fingerprint=digest, schema_version='scoped-v3-c5')
        from tools.conversion_tools.scoped_workflow.connections import attach_scoped_connections
        return attach_scoped_connections(conn, config, closure, unit, profile, classpath_index)

    for step in closure.steps:
        if step.execution_kind == 'routing_only':
            continue
        element = sources.xml(step.source)
        attached = [call for call in calls if call['occurrence_id'] == step.source.definition_id]
        unit = make('configured_step', step.source.entity_id, step.source.definition_id, step.source.definition_id,
            ElementTree.tostring(element, encoding='unicode'),
            dict(attributes=dict(element.attrib), routes=closure.routing_graph[step.source.note],
                 return_body_switches=closure.return_body_switches.get(step.source.note, {}),
                 resolved_implementation=element.get('implClass') or mappings.get(element.get('id')) or mappings.get('opStep'),
                 implementation_mapping_key=element.get('id') if element.get('id') in mappings else 'opStep'), attached,
            {element.get('implClass') or mappings.get(element.get('id')) or mappings.get('opStep')}, [])
        units.append(unit)
        bindings[step.source.note] = unit.unit_id
    directions = [(role, kind, closure.format_roles[role]) for role, kind in (
        ('csRequestFormat', 'request_unformat'), ('csReplyFormat', 'response_format'),
        ('csErrorReplyFormat', 'response_format')) if role in closure.format_roles]
    responses = {identity for _, kind, identity in directions if kind == 'response_format'}
    switched = {identity for switches in closure.return_body_switches.values() for identity in switches.values()}
    directions.extend(('return-format:' + identity, 'response_format', identity) for identity in sorted(switched - responses))
    for role, kind, identity in directions:
        node = closure.formats[identity]
        reference = access.resource(context, 'formats:' + node.attributes['id'])
        if reference.definition_id != identity:
            raise ValueError('Format role no longer selects the closure definition: ' + role)
        roots, definitions = format_evidence(closure, identity)
        unit = make(kind, reference.entity_id, role, identity,
            ElementTree.tostring(sources.xml(reference), encoding='unicode'), node.model_dump(mode='json'), (),
            roots, definitions)
        units.append(unit)
        bindings[role] = unit.unit_id
        if kind == 'response_format':
            bindings.setdefault('format:' + identity, unit.unit_id)
    if not units:
        raise ValueError('No configured behavior units were discovered')
    return units, bindings


def restore_cached_source_text(operation):
    """Restore exact source text in memory after immutable cache and file checks succeed."""
    origins={origin['definition_id']:origin for origin in operation['behavior_request']['java_origins']
             if origin['status']=='verified_source'}
    for unit in operation['units']:
        for source in unit['sources']:
            origin=origins[source['identity']]
            if source['content_hash']!=origin['source_hash']:
                raise ValueError('Cached source revision differs from original evidence')
            content=read_java_source(origin['source_file'],expected_hash=source['content_hash'],preserve_line_endings=True)
            normalized=content.replace('\r\n','\n').replace('\r','\n')
            if source['content'] not in (content,normalized):
                raise ValueError('Cached source content differs from original evidence')
            source['content']=content
