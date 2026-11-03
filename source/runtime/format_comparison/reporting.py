"""Behavior-only observations and truthful diagnostic reports, separate from acceptance."""
from collections import Counter
import json
from xml.parsers.expat import ExpatError
from tools.behavior_verification.boundary_comparison import compare_boundary_observations
from tools.behavior_verification.boundary_xml import xml_structure


def branch_results(case, probes):
    """Executing a condition is not evidence that its intended outcome was exercised."""
    result = {}
    for branch in case.targeted_branch_ids:
        expected = case.targeted_branch_outcomes.get(branch)
        observed = sorted({probe['outcome'] for probe in probes if probe.get('id') == branch and 'outcome' in probe})
        result[branch] = dict(expected_outcome=expected, observed_outcomes=observed,
                             status='observed' if expected is not None and expected in observed else 'targeted_not_confirmed')
    return result


def compare_case(left, right, direction, settings):
    """Compare final values/state; retain internal event counts and exception text as diagnostics."""
    if left.status != 'completed' or right.status != 'completed' or left.failure_origin or right.failure_origin:
        return dict(status='comparison_unavailable', differences=[], limitations=left.issues + right.issues,
                    reason='The adapter did not establish comparable production observations')
    a, b = left.model_copy(deep=True), right.model_copy(deep=True)
    limitations = []
    # Local variable assignments need not mimic Context writes. The raw events remain in the report.
    a.writes = []; b.writes = []; a.removals = []; b.removals = []
    if a.exception is not None or b.exception is not None:
        a.context = {}; b.context = {}
        limitations.append('Partial state on exception is not compared')
    differences = compare_boundary_observations(a, b, xml_output=direction == 'format')
    if settings.compare_exception_messages and left.exception and right.exception and left.exception.get('message') != right.exception.get('message'):
        differences.append(dict(path='exception.message', legacy=left.exception.get('message'), native=right.exception.get('message')))
    result = dict(status='different' if differences else 'comparison_unavailable' if limitations else 'matched',
                  differences=differences, limitations=limitations)
    if direction == 'format' and isinstance(left.output, str) and isinstance(right.output, str):
        result['xml_exact_match'] = left.output == right.output
        try:
            result['xml_structure_match'] = xml_structure(left.output) == xml_structure(right.output)
            result['xml_valid'] = True
        except (ValueError, ExpatError):
            result.update(xml_structure_match=None, xml_valid=False)
            result['limitations'].append('At least one output is not comparable valid XML')
            if result['status'] == 'matched':
                result['status'] = 'comparison_unavailable'
    return result


def publish(report, directory):
    """Write raw machine results plus a concise human checklist without acceptance side effects."""
    counts = Counter(case['status'] for case in report['cases'])
    report['counts'] = {name: counts.get(name, 0) for name in ('matched', 'different', 'comparison_unavailable', 'execution_failed')}
    report['counts']['planned'] = report.get('planned_cases', len(report['cases']))
    report['counts']['unexecuted'] = report['counts']['planned'] - len(report['cases'])
    (directory / 'format-comparison.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
    lines = [f"Format comparison: {report['label']}", '', 'Diagnostic only. Conversion acceptance is unchanged.', '',
             *[f'- {name}: {count}' for name, count in report['counts'].items()], '',
             'Limitations:', *['- ' + item for item in report.get('limitations', [])]]
    for item in report['cases']:
        marker = {'matched': 'V', 'different': 'X', 'comparison_unavailable': ' ', 'execution_failed': 'X'}[item['status']]
        lines.append(f"[{marker}] {item['case']['case_id']}: {item['status']}")
    (directory / 'format-comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

