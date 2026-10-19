"""Resolve bounded Java service-name expressions from configured unit evidence."""

import json
import re
from runtime.java_public_type import _code
from tools.validation_tools.java_comments import mask_java_comments


def service_lookups(source, parameters):
    """Return literal/configured lookups and retain unresolved dynamic expressions.

    Only bounded string assignments and simple equality-controlled branches are
    evaluated. Arbitrary Java control flow is not treated as a resolved constant.
    """
    text, code = mask_java_comments(source), _code(source)
    values = {}
    assignments = re.findall(r'\b(\w+)\s*=(?!=)', code)
    repeated = {name for name in assignments if assignments.count(name) > 1}

    def value(expression):
        expression = expression.strip().removesuffix('.toString()').strip()
        literal = re.fullmatch(r'"(?:\\.|[^"\\])*"', expression)
        if literal:
            try:
                return json.loads(expression)
            except ValueError:
                return None
        parameter = re.search(r'getParams\s*\(\s*\)\s*\.\s*(?:tryGetValueAt|getValueAt)\s*\(\s*"([^"\\]+)"\s*\)', expression)
        if parameter:
            return parameters.get(parameter[1])
        return values.get(expression)

    for _ in range(3):
        for match in re.finditer(r'\b(?:String|java\.lang\.String)\s+(\w+)\s*=\s*([^;]+);', text):
            if match[1] in repeated:
                continue  # Reassignment needs data-flow analysis; never guess its value.
            if not code[match.start():match.start() + 1].strip():
                continue
            expression = re.sub(r'^\s*\(\s*(?:String|java\.lang\.String)\s*\)\s*', '', match[2])
            resolved = value(expression)
            if isinstance(resolved, str):
                values[match[1]] = resolved
    # The demonstrated helper returns true for one configured service-name value.
    booleans = {}
    for method in re.finditer(r'\bboolean\s+(\w+)\s*\(\s*\)\s*\{', code):
        depth, end = 1, method.end()
        while end < len(code) and depth:
            depth += (code[end] == '{') - (code[end] == '}')
            end += 1
        body = text[method.end():end - 1]
        equality = re.search(r'\b(\w+)\s*\.\s*equals\s*\(\s*("[^"\\]+")\s*\)', body)
        supported = re.fullmatch(r'\s*(?:String\s+\w+\s*=\s*[^;]+;\s*)?'
            r'if\s*\(\s*\w+\s*!=\s*null\s*&&\s*\w+\.equals\s*\(\s*"[^"\\]+"\s*\)\s*\)\s*'
            r'\{?\s*return\s+true\s*;\s*\}?\s*return\s+false\s*;\s*', body)
        if equality and supported:
            actual = values.get(equality[1])
            if actual is not None:
                booleans[method[1] + '()'] = actual == json.loads(equality[2])
    for assignment in re.finditer(r'\b(\w+)\s*=\s*(\w+\(\))\s*;', code):
        if assignment[2] in booleans:
            booleans[assignment[1]] = booleans[assignment[2]]
    excluded = []
    for branch in re.finditer(r'\bif\s*\(\s*(\w+(?:\(\))?)\s*\)\s*\{([^{}]*)\}\s*else\s*\{([^{}]*)\}', code):
        if branch[1] in booleans:
            excluded.append(branch.span(3 if booleans[branch[1]] else 2))
    lookups = []
    for match in re.finditer(r'\bgetService\s*\(', code):
        prefix = code[:match.start()]
        receiver = re.search(r'\b(\w+)\s*\.\s*$', prefix)
        if receiver and not re.search(r'\b(?:[\w.]*Context\s+' + re.escape(receiver[1]) +
            r'\b|(?:var\s+)?' + re.escape(receiver[1]) + r'\s*=\s*getContext\s*\()', code):
            continue
        if re.search(r'\b(?:public|protected|private)\s+[\w.<>]+\s*$', prefix):
            continue  # Method declarations are not service lookups.
        if any(start <= match.start() < end for start, end in excluded):
            continue
        depth, end = 1, match.end()
        while end < len(code) and depth:
            depth += (code[end] == '(') - (code[end] == ')')
            end += 1
        expression = text[match.end():end - 1].strip()
        name = value(expression)
        lookups.append(dict(service_name=name, expression=expression,
                            line=text[:match.start()].count('\n') + 1,
                            condition='configured branch' if excluded else 'reachable lookup'))
    return lookups
