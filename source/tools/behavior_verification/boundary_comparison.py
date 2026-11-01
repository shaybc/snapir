"""Compare declared boundary observables, independently of internal implementation structure."""
from xml.parsers.expat import ExpatError
from tools.behavior_verification.boundary_xml import xml_structure
from tools.behavior_verification.boundary_logging import compare_logging


def compare_boundary_observations(legacy, native, *, xml_output=False, insignificant_whitespace_paths=(), logging_diagnostics=None):
    differences = []
    if legacy.status != 'completed' or native.status != 'completed':
        return [dict(path='execution', legacy=legacy.status, native=native.status, reason='Verification incomplete')]
    expected, actual = legacy.model_dump(mode='json'), native.model_dump(mode='json')
    for name in ('output', 'context', 'writes', 'removals', 'external_calls', 'exception'):
        left, right = expected[name], actual[name]
        if name == 'external_calls':
            left, right, logging_differences, diagnostics = compare_logging(left, right)
            differences.extend(logging_differences)
            if logging_diagnostics is not None: logging_diagnostics.extend(diagnostics)
        if name == 'exception':
            left = None if left is None else {'type': left['type']}
            right = None if right is None else {'type': right['type']}
        if name == 'output' and isinstance(left, str) and left == right:
            continue
        if name == 'output' and xml_output and isinstance(left, str) and isinstance(right, str) and left.lstrip().startswith('<'):
            try:
                if xml_structure(left, insignificant_whitespace_paths) == xml_structure(right, insignificant_whitespace_paths): continue
            except (ValueError, ExpatError) as error:
                differences.append(dict(path='output.xml', legacy=left, native=right, reason='XML comparison failed: ' + str(error)))
                continue
        _diff(left, right, name, differences)
    return differences


def boundary_field_results(legacy, native, differences):
    """Name matching fields too; absent and explicitly null fields keep separate presence flags."""
    fields = ['output', 'exception', 'writes', 'removals', 'external_calls', 'logging']
    fields += ['context.' + key for key in sorted(set(legacy.context) | set(native.context))]
    results = []
    for field in fields:
        compared = legacy.status == native.status == 'completed'
        matched = compared and not any(item['path'] == field or item['path'].startswith(field + '.')
            or item['path'].startswith(field + '[') for item in differences)
        item = dict(field=field, result='matched' if matched else 'different' if compared else 'not_compared')
        if field.startswith('context.'):
            key = field[len('context.'):]
            item.update(legacy_present=key in legacy.context, native_present=key in native.context)
        results.append(item)
    return results


def _diff(left, right, path, differences):
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append(dict(path=path + '.' + key, legacy=left.get(key), native=right.get(key),
                                        reason='Missing field on ' + ('legacy' if key not in left else 'native') + ' side'))
            else: _diff(left[key], right[key], path + '.' + key, differences)
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right): differences.append(dict(path=path + '.length', legacy=len(left), native=len(right), reason='Event/value count differs'))
        for index, (a, b) in enumerate(zip(left, right)): _diff(a, b, path + '[' + str(index) + ']', differences)
    elif type(left) != type(right) or left != right:
        differences.append(dict(path=path, legacy=left, native=right, reason='Observable value differs'))

