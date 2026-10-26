"""Carry scoped occurrence evidence into behavior, assembly, and route-test requests."""

from xml.etree import ElementTree
from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence


def operation_payload(config, closure, contract, calls, units, bindings):
    """Prepare one workflow description shared by both generation paths, still gated."""
    sources = SourceEvidence(config.source_root)
    steps = []
    for step in closure.steps:
        element = sources.xml(step.source)
        steps.append(dict(occurrence_id=step.source.definition_id, note=step.source.note,
            business_name=step.source.entity_id, source_index=step.source_index, effective_index=step.effective_index,
            attributes=dict(element.attrib), configuration_xml=ElementTree.tostring(element, encoding='unicode'),
            unit_id=bindings.get(step.source.note), routes=closure.routing_graph[step.source.note],
            return_body_switches=closure.return_body_switches.get(step.source.note, {}),
            return_body_units={condition: bindings['format:' + identity] for condition, identity in
                               closure.return_body_switches.get(step.source.note, {}).items()}))
    requirements = dict(operation_flow='Preserve source order, initialization, side effects and final steps.',
        effective_configuration='Use effective format trees and selected occurrences; raw XML is provenance, not a second selection policy.',
        outcome_precedence='Preserve evidenced timeout, error and onOther handling; do not invent missing routes.',
        return_body_switches='Preserve occurrence-specific response/error-body selection and restoration.',
        native_calls='Use accepted native Java methods directly; preserve the existing HTTP call contract for complex calls.')
    if calls:
        from runtime.behavior_conversion.operation_calls import INSTRUCTION
        requirements['operation_calls'] = INSTRUCTION
    if any(unit.service_connections for unit in units):
        from runtime.behavior_conversion.service_connection_evidence import SERVICE_CONNECTION_INSTRUCTION
        requirements['service_connections'] = SERVICE_CONNECTION_INSTRUCTION
    for step in steps:
        requirements['route-' + step['occurrence_id']] = dict(attributes=step['attributes'], routes=step['routes'],
            return_body_switches=step['return_body_switches'])
    workflow = dict(operation_identity=closure.operation_identity, operation_key=closure.channel + '/' + closure.operation_id,
        operation_id=closure.operation_id,
        channel=closure.channel, definition_id=closure.definition_id, operation_attributes=closure.operation['attributes'],
        operation_source=closure.operation['source'],
        entry_step_note=closure.entry_step_note, steps=steps, unit_bindings=bindings,
        routing_graph=closure.routing_graph, format_roles=closure.format_roles,
        formats={key: node.model_dump(mode='json') for key, node in closure.formats.items()},
        context_chain=closure.context_chain, context_fields=closure.context_fields,
        java_origins=closure.java_origins, external_dependencies=closure.external_dependencies,
        composer_behavior_evidence=closure.composer_behavior_evidence,
        service_connections=[dict(unit_id=unit.unit_id, occurrence_id=unit.occurrence_id,
                                  connections=unit.service_connections) for unit in units if unit.service_connections],
        operation_calls=calls, service_contract=contract, requirements=requirements,
        evidence_hash=closure.evidence_hash, conversion_enabled=False)
    # Both engines receive identical routing facts, not a label-keyed legacy projection.
    return dict(behavior_request=workflow, assembly_request=dict(workflow),
        route_test_request=dict(operation_identity=closure.operation_identity, entry_step_note=closure.entry_step_note,
            steps=steps, requirements=requirements, operation_calls=calls),
        units=[unit.model_dump(mode='json') for unit in units])
