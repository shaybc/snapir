"""Extract, reconcile and persist source obligations before scoped native generation."""

import hashlib
import json

from agents.behavior_conversion.behavior_extraction import EXTRACT, POLICY, RECONCILE
from models.behavior_specification import BehaviorSpecification, BehaviorReconciliation
from runtime.behavior_conversion.behavior_fact_validation import validate_specification
from runtime.behavior_conversion.request_context import bundle_parts
from tools.component_inventory_tools.identity import stable_id


def evidence_catalog(payload, identity):
    """Collect original code and explicit configuration/policy, never generated sources."""
    sources = {}
    for source in [*payload.get('sources', []), *payload.get('operation_sources', []),
                   *payload.get('behavior_evidence', [])]:
        if source['identity'] in sources and sources[source['identity']] != source:
            raise ValueError('Conflicting original behavior evidence identity')
        sources[source['identity']] = source
    if not payload.get('behavior_evidence'):
        configuration = {key: payload[key] for key in (
            'configuration_xml', 'effective_configuration', 'referenced_definitions', 'closure',
            'external_dependencies', 'service_connections', 'operation_calls') if key in payload}
        text = json.dumps(configuration, sort_keys=True, ensure_ascii=False)
        policy = POLICY
        if payload.get('agreed_behavior_requirements'):
            policy += '\nAgreed requirements: ' + json.dumps(payload['agreed_behavior_requirements'], sort_keys=True)
        for name, content in [(identity + ':configuration', text), ('compatibility-policy:observable-v1', policy)]:
            sources[name] = dict(identity=name, content=content,
                                 content_hash=hashlib.sha256(content.encode('utf-8')).hexdigest())
    return list(sources.values())


def extract_behavior(conn, config, profile, identity, payload, model_call=None):
    """Read bounded original evidence and keep all validated facts through reconciliation."""
    from runtime.behavior_conversion.generation import generate
    kind = payload.get('kind', 'service')
    agreed = {item.requirement_id: dict(description=item.description, version=item.version)
              for item in getattr(profile, 'conversion_requirements', [])
              if '*' in item.applies_to or kind in item.applies_to}
    payload = dict(payload, agreed_behavior_requirements=agreed)
    sources = evidence_catalog(payload, identity)
    if payload.get('source_summaries'):
        raise ValueError('Behavior extraction requires original source, not lossy source summaries')
    scope = {key: payload[key] for key in ('kind', 'schema_version', 'logical_id', 'configuration_xml',
             'effective_configuration', 'referenced_definitions', 'closure',
             'agreed_behavior_requirements') if key in payload}
    parts = bundle_parts(dict(subject_id=identity, subject_scope=scope, sources=sources), EXTRACT,
                         BehaviorSpecification.model_json_schema(), profile.behavior_context_chars)
    facts, questions, fingerprints = {}, [], []
    for part in parts:
        def validate(specification, cached=False):
            validate_specification(specification, part['sources'])
        specification, fingerprint = generate(conn, config, profile, 'behavior_extraction',
            identity + ':facts-part:' + str(part['part']), EXTRACT, part, BehaviorSpecification,
            validate, model_call, 'Source behavior: ' + identity)
        facts.update({fact.fact_id: fact for fact in specification.facts})
        questions.extend(specification.unresolved_questions)
        fingerprints.append(fingerprint)
    if len(parts) > 1:
        def validate_reconciliation(result, cached=False):
            if not set(result.conflicting_fact_ids).issubset(facts):
                raise ValueError('Reconciliation cites an unknown fact')
        reconciliation, fingerprint = generate(conn, config, profile, 'behavior_extraction',
            identity + ':facts-reconcile', RECONCILE,
            dict(subject_id=identity, facts=[fact.model_dump(mode='json') for fact in facts.values()]),
            BehaviorReconciliation, validate_reconciliation, model_call, 'Reconcile source behavior: ' + identity)
        fingerprints.append(fingerprint)
        questions.extend(reconciliation.unresolved_questions)
        questions.extend('Conflicting source behavior: ' + key for key in reconciliation.conflicting_fact_ids)
    result = BehaviorSpecification(facts=[facts[key] for key in sorted(facts)],
                                   unresolved_questions=list(dict.fromkeys(questions)))
    fingerprint = stable_id(fingerprints, EXTRACT, RECONCILE, POLICY)
    from tools.state_store_tools.behavior_units import save
    save(conn, config.run_id, 'behavior_specification', identity, fingerprint,
         dict(specification=result.model_dump(mode='json'),
              sources=[{key: source[key] for key in ('identity', 'content_hash')} for source in sources]))
    return result, fingerprint, sources


def attach_behavior_specification(conn, config, profile, identity, payload, model_call=None):
    """Add grounded obligations without replacing relevant original code evidence."""
    specification, fingerprint, sources = extract_behavior(conn, config, profile, identity, payload, model_call)
    if specification.unresolved_questions:
        raise ValueError('Source behavior evidence is unresolved: ' + '; '.join(specification.unresolved_questions))
    present = {source['identity'] for source in [*payload.get('sources', []), *payload.get('operation_sources', [])]}
    return dict(payload, behavior_specification=specification.model_dump(mode='json'),
        behavior_specification_fingerprint=fingerprint,
        behavior_evidence=[source for source in sources if source['identity'] not in present])
