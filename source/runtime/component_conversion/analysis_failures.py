"""Preserve explicit analyzer causes across component and dependency failures."""


class ComponentAnalysisBlocked(ValueError):
    """A component cannot be prepared because its boundary analysis failed."""
    def __init__(self, cause_ids, message, *, role='analysis_consequence'):
        self.failure_role = role
        self.root_cause_ids = sorted(set(cause_ids))
        super().__init__(message)


def require_analysis(plan, group, boundaries):
    """Reject missing analysis with its recorded cause before generic entry checks."""
    units = {unit for key in group.members for unit in plan.components[key].unit_ids}
    affected = {boundary.get('analysis_failure_id') for boundary in boundaries.get('boundaries', {}).values()
                if boundary.get('unit_id') in units}
    # Boundary keys are authoritative even when a saved record omits unit_id.
    affected.update(boundary.get('analysis_failure_id') for key, boundary in boundaries.get('boundaries', {}).items() if key in units)
    failures = [failure for failure in boundaries.get('analysis_failures', []) if failure['id'] in affected]
    if failures:
        raise ComponentAnalysisBlocked([failure['id'] for failure in failures],
            'Blocked by underlying analysis failure: ' + '; '.join(failure['message'] for failure in failures))


def failure_result(group, error):
    """Only correlate recorded analysis failures and explicit prerequisite failures."""
    result = dict(status='incomplete', members=group.members, reason=str(error))
    causes = getattr(error, 'root_cause_ids', [])
    if causes: result.update(failure_role=error.failure_role, root_cause_ids=causes)
    return result


def require_prerequisites(group, report):
    """Stop dependent work when a prerequisite has a recorded analysis cause."""
    blocked = {key: report['groups'].get(key, {}) for key in group.dependencies
               if report['groups'].get(key, {}).get('root_cause_ids')}
    if not blocked: return
    raise ComponentAnalysisBlocked([cause for item in blocked.values() for cause in item['root_cause_ids']],
        'Required prerequisites blocked by underlying analysis failure: ' + ', '.join(sorted(blocked)),
        role='dependency_consequence')
