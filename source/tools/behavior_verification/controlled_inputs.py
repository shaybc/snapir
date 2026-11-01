"""Deterministic configuration/literal-driven cases; counts do not imply path coverage."""
import hashlib
import json
import random
import re
from xml.sax.saxutils import escape
from models.boundary_case import BoundaryCase


def generate_boundary_cases(unit, boundary, *, seed=1729, settings=(), random_cases=12, context_defaults=None,
                            context_class='com.ibm.dse.base.Context', context_reader='getValueAt', context_remover='removeValueAt', baseline_only=False):
    """Vary each configured field independently, then add seeded combinations."""
    configuration = unit['effective_configuration']
    fields = {}

    def visit(node):
        children = node.get('children', [])
        name = node.get('attributes', {}).get('dataName')
        if not children and name:
            fields[name] = node.get('attributes', {})
        for child in children: visit(child)

    visit(configuration)
    if unit['kind'] != 'request_unformat':
        return _context_cases(unit, boundary, fields, seed, settings, random_cases, context_defaults or {},
                              context_class, context_reader, context_remover,baseline_only)
    if not fields:
        raise ValueError('Automatic request cases require configured fields; supply explicit cases for this boundary')
    roots = configuration.get('children', []) if configuration.get('tag') == 'fmtDef' else [configuration]
    root_name = roots[0].get('attributes', {}).get('dataName') if len(roots) == 1 else None
    if not root_name or not all(re.fullmatch(r'[A-Za-z_][\w.-]*', name) for name in [root_name, *fields]):
        raise ValueError('Automatic request cases require explicit simple XML element names')
    baseline = {}
    for name, attributes in fields.items():
        pattern = attributes.get('pattern', '')
        baseline[name] = _pattern_value(pattern) if pattern else '123'
    literals = [item.properties.get('value', '') for item in boundary.parser_checklist.items if item.kind == 'literal']
    values = [None, '', ' ', '0', '1', '-1', '0005', ' 123 ', 'a&<b>', '20240102', 'invalid']
    values += [value for value in literals if re.fullmatch(r'-?\d{1,8}', value) and value not in values][:8]
    rng = random.Random(seed)
    candidates = [('baseline', baseline)]
    for name in fields:
        for value in values:
            candidates.append((name, {**baseline, name: value}))
    for _ in range(random_cases):
        candidates.append(('seeded_combination', {name: rng.choice(values) for name in fields}))
    result = []
    for index, (label, row) in enumerate(candidates):
        xml = '<' + root_name + '>' + ''.join('<' + name + '>' + escape(value) + '</' + name + '>'
            for name, value in row.items() if value is not None) + '</' + root_name + '>'
        identity = hashlib.sha256((str(seed) + ':' + str(index) + ':' + xml).encode()).hexdigest()[:16]
        result.append(BoundaryCase(case_id=identity, input_xml=xml, random_seed=seed,
            settings=list(settings), labels=[label, 'missing_element' if None in row.values() else 'present_elements']))
    return result


def _context_cases(unit, boundary, fields, seed, settings, random_cases, defaults, context_class, reader, remover,baseline_only=False):
    """Use evidenced context keys, not a class-specific formatter/step behavior catalog."""
    def indexed(node):
        return node.get('collection_kind') == 'indexed' or any(indexed(child) for child in node.get('children', []))
    if indexed(unit['effective_configuration']):
        raise ValueError('Structured collection inputs require an explicit case adapter')
    literals = {item.excerpt: item.properties.get('value') for item in boundary.parser_checklist.items
                if item.kind == 'literal' and item.detail == 'StringLiteralExpr'}
    baseline = {name: {'$date_millis': 1704153600000} if attributes.get('pattern') else '123'
                for name, attributes in fields.items()}
    for item in boundary.parser_checklist.items:
        target = item.properties.get('target', '')
        if (item.kind == 'call' and any(target.startswith(context_class + '.' + name + '(') for name in (reader, remover))
                and len(item.arguments) == 1 and item.arguments[0] in literals):
            baseline.setdefault(literals[item.arguments[0]], '123')
    baseline.update(defaults)
    if baseline_only:return [BoundaryCase(case_id='baseline',initial_context=baseline,settings=list(settings),random_seed=seed,labels=['baseline'])]
    values = [None, '', ' ', '0', '1', '-1', '0005', ' 123 ', 'a&<b>', '20240102', 'invalid']
    rows = [('baseline', baseline)]
    for name in baseline:
        for value in values: rows.append((name, {**baseline, name: value}))
        rows.append((name + ':missing', {key: value for key, value in baseline.items() if key != name}))
    rng = random.Random(seed)
    for _ in range(random_cases): rows.append(('seeded_combination', {name: rng.choice(values) for name in baseline}))
    seen, cases = set(), []
    for label, row in rows:
        encoded = json.dumps(row, sort_keys=True)
        if encoded in seen: continue
        seen.add(encoded)
        identity = hashlib.sha256((str(seed) + ':' + encoded).encode()).hexdigest()[:16]
        cases.append(BoundaryCase(case_id=identity, initial_context=row, settings=list(settings), random_seed=seed, labels=[label]))
    return cases


def _pattern_value(pattern):
    values = {'yyyy': '2024', 'yy': '24', 'MM': '01', 'dd': '02', 'HH': '03', 'mm': '04', 'ss': '05', 'SSS': '006'}
    pieces = [match.group(0) for match in re.finditer(r"([A-Za-z])\1*|[^A-Za-z]+", pattern)]
    if not pieces or any(piece.isalpha() and piece not in values for piece in pieces):
        raise ValueError('Automatic baseline cannot format pattern: ' + pattern)
    return ''.join(values.get(piece, piece) for piece in pieces)

