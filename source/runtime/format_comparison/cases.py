"""Generate branch fixtures as data, preserving unresolved dependencies and presence."""
from copy import deepcopy
from models.format_comparison_case import FormatComparisonCase
from tools.behavior_verification.boundary_contracts import digest
from runtime.format_comparison.context_discovery import validate_discovery, validate_citations, evidence_catalog,applies_to_direction


def expand_fixtures(plan, settings):
    """Overlay one source-backed/exploratory branch value per supplied baseline; never infer outputs."""
    validate_discovery(plan.discovery, plan.original_unit)
    cases = list(plan.cases)
    if getattr(plan,'explicit_scenarios',False):
        if len(cases)>settings.max_cases:raise ValueError('Declared scenarios exceed the case budget; no cases dropped')
        return cases
    for case in cases:
        validate_citations(case.citations, evidence_catalog(plan.original_unit))
        if case.origin == 'source_backed' and not case.citations:
            raise ValueError('Source-backed fixture requires exact original evidence')
    seen = {case.case_id for case in cases}
    for baseline in plan.cases:
        required = set(baseline.required_inputs) if baseline.required_inputs is not None else None
        for requirement in plan.discovery.requirements:
            if not applies_to_direction(requirement,plan.entries[baseline.binding_id].direction):
                continue
            if required is not None and requirement.requirement_id not in required:
                continue
            if requirement.context_key is None or requirement.unresolved_reason:
                continue
            for candidate in requirement.values:
                identity = 'branch-' + digest((baseline.case_id, requirement.requirement_id, candidate.model_dump(mode='json')))[:24]
                if identity in seen:
                    continue
                seen.add(identity)
                value = baseline.model_dump(mode='json')
                value.update(case_id=identity, origin=candidate.origin,
                             citations=[citation.model_dump(mode='json') for citation in candidate.citations],
                             targeted_branch_ids=[candidate.branch_id] if candidate.branch_id else [],
                             targeted_branch_outcomes={candidate.branch_id: candidate.branch_outcome} if candidate.branch_id and candidate.branch_outcome is not None else {})
                value['initial_context'] = deepcopy(baseline.initial_context)
                value['initial_context'][requirement.context_key] = candidate.value
                value['intentionally_absent'] = [key for key in baseline.intentionally_absent if key != requirement.context_key]
                cases.append(FormatComparisonCase.model_validate(value))
    if len(cases) > settings.max_cases:
        raise ValueError('Planned fixtures exceed the configured case budget; no cases were silently dropped')
    return cases


def unresolved_inputs(plan, case):
    """An unresolved required input prevents that case, while independent cases may execute."""
    selected = case.required_inputs
    issues = []
    issues.extend(getattr(case,'scenario_unresolved',[]))
    requirements = {item.requirement_id: item for item in plan.discovery.requirements}
    if selected is not None:
        issues.extend('Unknown input requirement: ' + key for key in selected if key not in requirements)
    for key, requirement in requirements.items():
        if not applies_to_direction(requirement,plan.entries[case.binding_id].direction):
            continue
        if selected is not None and key not in selected:
            continue
        if requirement.unresolved_reason or requirement.context_key is None:
            issues.append(key + ': ' + (requirement.unresolved_reason or 'Unresolved context path'))
        elif requirement.required and requirement.context_key not in case.initial_context and requirement.context_key not in case.intentionally_absent:
            issues.append(key + ': Required input is absent: ' + requirement.context_key)
    if selected is None:
        issues.extend(plan.discovery.unresolved)
    return issues

