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
    implementations = []
    for origin in closure.java_origins:
        if origin['status'] != 'verified_source':
            continue
        identity = (origin['definition_id'], origin['source_hash'])
        # The guarded read checks current bytes even when another context used this source.
        content = read_java_source(origin['source_file'], expected_hash=origin['source_hash'])
        if identity not in cache:
            cache[identity] = UnitSource(identity=identity[0], content=content, content_hash=identity[1])
        implementations.append(cache[identity])
    definitions = [node.model_dump(mode='json') for _, node in sorted(closure.formats.items())]
    units, bindings = [], {}
    from tools.conversion_tools.scoped_reuse.fingerprints import POLICY_VERSION, conversion_policy
    policy = conversion_policy(profile)

    def make(kind, label, occurrence, definition, xml, configuration, attached_calls):
        facts = dict(policy_version=POLICY_VERSION, conversion_policy=policy,
            operation_identity=closure.operation_identity, occurrence_id=occurrence,
            source_definition_id=definition, kind=kind, configuration=configuration,
            closure_evidence_hash=closure.evidence_hash, calls=list(attached_calls),
            java_origins=closure.java_origins, external_dependencies=closure.external_dependencies)
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
        unit = ScopedConfiguredUnit(unit_id='scoped-unit-' + digest, kind=kind, logical_id=label,
            operation_identity=closure.operation_identity, occurrence_id=occurrence, source_definition_id=definition,
            effective_configuration=configuration,
            configuration_xml=xml, sources=implementations, consumers=[closure.channel + '/' + closure.operation_id],
            referenced_definitions=definitions, external_dependencies=closure.external_dependencies,
            operation_calls=list(attached_calls), fingerprint=digest, schema_version='scoped-v3-c5')
        from tools.conversion_tools.scoped_workflow.connections import attach_scoped_connections
        return attach_scoped_connections(conn, config, closure, unit, profile, classpath_index)

    for step in closure.steps:
        element = sources.xml(step.source)
        attached = [call for call in calls if call['occurrence_id'] == step.source.definition_id]
        unit = make('configured_step', step.source.entity_id, step.source.definition_id, step.source.definition_id,
            ElementTree.tostring(element, encoding='unicode'),
            dict(attributes=dict(element.attrib), routes=closure.routing_graph[step.source.note],
                 return_body_switches=closure.return_body_switches.get(step.source.note, {})), attached)
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
        unit = make(kind, reference.entity_id, role, identity,
            ElementTree.tostring(sources.xml(reference), encoding='unicode'), node.model_dump(mode='json'), ())
        units.append(unit)
        bindings[role] = unit.unit_id
        if kind == 'response_format':
            bindings.setdefault('format:' + identity, unit.unit_id)
    if not units:
        raise ValueError('No configured behavior units were discovered')
    return units, bindings
