"""Resolve diagnostic source/configuration snapshots without registering conversion tasks."""
from copy import deepcopy
import hashlib
from tools.behavior_verification.boundary_contracts import boundary_contract, digest
from tools.behavior_verification.boundaries import build_boundary_report
from models.unit_verification_boundary import UnitVerificationBoundary


def original_unit(sources, configuration, *, references=(), label='format'):
    """Create a standalone unit from existing source evidence and a resolved configuration tree."""
    for source in sources:
        if hashlib.sha256(source['content'].encode('utf-8')).hexdigest() != source['content_hash']:
            raise ValueError('Original source bytes/hash mismatch: ' + source['identity'])
    return dict(unit_id='diagnostic-' + digest((label, configuration))[:20], fingerprint=digest(sources),
                operation_identity='standalone-format-diagnostic', kind='response_format',
                effective_configuration=deepcopy(configuration), configuration_xml='',
                referenced_definitions=deepcopy(list(references)), sources=deepcopy(sources))


def unit_for_case(plan, case):
    """Apply a declared configuration variant to the actual selected root, not a guessed child."""
    unit = deepcopy(plan.original_unit)
    if len({source['identity'] for source in unit['sources']}) != len(unit['sources']):
        raise ValueError('Duplicate original source identity')
    for source in unit['sources']:
        if hashlib.sha256(source['content'].encode('utf-8')).hexdigest() != source['content_hash']:
            raise ValueError('Original source hash does not match supplied bytes')
    if plan.scope == 'basic':
        unit['format_scope'] = 'basic'
        node = unit['effective_configuration']
        if node.get('children') or node.get('decorators') or not node.get('java_class'):
            raise ValueError('Basic comparison requires an explicit undecorated implementing root')
    if case.configuration_attributes is not None:
        node = unit['effective_configuration']
        if not node.get('java_class'):
            raise ValueError('Configuration variants require an explicit implementing root')
        node['attributes'] = deepcopy(case.configuration_attributes)
    unit['kind'] = {'format': 'response_format', 'unformat': 'request_unformat','step_execute':'configured_step'}[plan.entries[case.binding_id].direction]
    # Case grouping includes direction and configuration; source identity remains intact.
    unit['unit_id'] = 'diagnostic-' + digest((plan.label, unit['kind'], unit['effective_configuration']))[:20]
    return unit


def analyze_unit(unit, tool, *, collect_facts=True, step_implementation=None):
    """Reuse parser/reachability discovery for real instrumentation and observed branch probes."""
    report = build_boundary_report({'operations': {'diagnostic': {'units': [unit]}}}, tool_jar=tool,
                                  collect_checklists=collect_facts,**({'mappings':{'opStep':step_implementation}} if step_implementation else {}))
    boundary = UnitVerificationBoundary.model_validate(report['boundaries'][unit['unit_id']])
    if boundary.analysis_status != 'identified' or boundary.issues:
        raise ValueError('Original boundary cannot be identified: ' + '; '.join(boundary.issues))
    current = boundary_contract(unit,{'opStep':step_implementation} if step_implementation else None)
    if boundary.source_manifest_hash != current.source_manifest_hash or boundary.configuration_hash != current.configuration_hash:
        raise ValueError('Source/configuration changed during analysis')
    return boundary

