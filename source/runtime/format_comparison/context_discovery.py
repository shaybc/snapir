"""Discover runtime inputs through bounded AI requests with literal evidence validation."""
import json
from models.format_context_requirement import FormatContextDiscovery
from agents.behavior_conversion.format_context_discovery import DISCOVERY
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes


def evidence_catalog(unit):
    """Expose original sources and resolved configuration, without native expectations."""
    catalog = {source['identity']: source['content'] for source in unit['sources']}
    if len(catalog) != len(unit['sources']):
        raise ValueError('Duplicate source evidence identities')
    catalog['configuration'] = json.dumps(unit['effective_configuration'], ensure_ascii=False, sort_keys=True)
    if unit.get('configuration_xml'):
        catalog['configuration_xml'] = unit['configuration_xml']
        for identity in {unit.get('source_definition_id'),unit.get('occurrence_id')} - {None,''}:
            if identity in catalog and catalog[identity]!=unit['configuration_xml']:
                raise ValueError('Conflicting configuration evidence identity: '+identity)
            catalog[identity] = unit['configuration_xml']
    for definition in unit.get('referenced_definitions', []):
        catalog['configuration:' + definition['definition_id']] = json.dumps(definition, ensure_ascii=False, sort_keys=True)
    return catalog


def validate_citations(citations, catalog):
    """Validate source identity and exact excerpt; this does not establish semantic truth."""
    for citation in citations:
        if not citation.excerpt.strip() or citation.excerpt not in catalog.get(citation.source_identity, ''):
            raise ValueError('Discovery citation is absent from supplied original evidence')


def validate_discovery(discovery, unit):
    """Reject invented citations, unsupported value claims and duplicate requirements."""
    catalog = evidence_catalog(unit)
    identities = [item.requirement_id for item in discovery.requirements]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate context requirement identity')
    for requirement in discovery.requirements:
        validate_citations(requirement.citations, catalog)
        for value in requirement.values:
            validate_citations(value.citations, catalog)
            if value.origin == 'source_backed' and not value.citations:
                raise ValueError('Source-backed input requires source/configuration evidence')
            expected = {'string': str, 'boolean': bool, 'integer': int, 'number': (int, float), 'list': list, 'map': dict}.get(requirement.value_type)
            if value.origin == 'source_backed' and value.value is not None and expected is not None:
                valid = isinstance(value.value, expected)
                if requirement.value_type in {'integer', 'number'} and isinstance(value.value, bool):
                    valid = False
                if not valid:
                    raise ValueError('Source-backed value contradicts the declared context input type')
    return discovery


def applies_to_direction(requirement, direction):
    """Scope new discovery labels while keeping historical unlabelled plans readable."""
    return requirement.directions is None or direction in requirement.directions


def discover_context(unit, model_call, settings, directory, *, directions=None):
    """Retain request/response artifacts; provider failure is an unresolved inventory."""
    selected=sorted(set(directions if directions is not None else
        ['unformat'] if unit.get('kind')=='request_unformat' else ['format']))
    if not selected or set(selected)-{'format','unformat'}:
        raise ValueError('Discovery requires explicit format/unformat directions')
    payload = dict(execution=dict(unit_kind=unit.get('kind'),selected_directions=selected,
        entry_points=[dict(direction=direction,method_name=direction) for direction in selected]),
        evidence=evidence_catalog(unit), schema=FormatContextDiscovery.model_json_schema())
    encoded = json.dumps(payload, ensure_ascii=True)
    if len(DISCOVERY) + len(encoded) > settings.discovery_request_chars:
        return FormatContextDiscovery(unresolved=[f'Discovery request exceeds configured character budget: total_chars={len(DISCOVERY) + len(encoded)}, limit_chars={settings.discovery_request_chars}'])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'request.json').write_text(encoded, encoding='utf-8')
    (directory / 'instruction.txt').write_text(DISCOVERY, encoding='utf-8')
    try:
        response = model_call(DISCOVERY, encoded)
        (directory / 'response.txt').write_text(response, encoding='utf-8')
        value = FormatContextDiscovery.model_validate_json(clean_structural_escapes(_remove_response_fence(response)))
        if any(not item.directions or len(set(item.directions))!=len(item.directions) or set(item.directions)-set(selected) for item in value.requirements):
            raise ValueError('Discovered inputs must identify their selected execution directions')
        return validate_discovery(value, unit)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        return FormatContextDiscovery(unresolved=['Context discovery failed: ' + type(error).__name__])

