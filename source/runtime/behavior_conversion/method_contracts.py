"""Match declared Java methods using resolved types rather than source spelling."""

import re
from runtime.java_public_type import _code, public_types

_IDENTIFIER = r"[A-Za-z_$][\w$]*"
_JAVA_LANG = set("String Object Boolean Byte Character Short Integer Long Float Double Void Number Class Enum Record Throwable Exception RuntimeException IllegalArgumentException Iterable Comparable CharSequence StringBuilder StringBuffer Math System AutoCloseable".split())
_MODIFIERS = set("public protected private static final abstract synchronized native strictfp default".split())


def _erase_type_arguments(text):
    """Remove nested generic arguments while preserving the raw type and array shape."""
    result, depth = [], 0
    for character in text:
        if character == '<':
            depth += 1
        elif character == '>':
            depth -= 1
            if depth < 0:
                raise ValueError('Unbalanced generic type in method contract: ' + text)
        elif depth == 0:
            result.append(character)
    if depth:
        raise ValueError('Unbalanced generic type in method contract: ' + text)
    return ''.join(result)


def _parameters(text):
    """Split parameter lists without splitting generic type arguments."""
    result, start, depth = [], 0, 0
    for index, character in enumerate(text):
        if character == '<':
            depth += 1
        elif character == '>':
            depth -= 1
        elif character == ',' and depth == 0:
            result.append(text[start:index])
            start = index + 1
    if text.strip():
        result.append(text[start:])
    return result


def _signature(text, resolve):
    """Represent name, return type, ordered parameter types and static membership."""
    text = re.sub(r"@" + _IDENTIFIER + r"(?:\." + _IDENTIFIER + r")*(?:\([^()]*\))?\s*", "", text)
    match = re.search(r"^(.*?)\b(" + _IDENTIFIER + r")\s*\((.*?)\)", text.strip(), re.S)
    if not match:
        return None
    prefix, name, parameters = match.groups()
    modifiers = set(re.findall(r"\b(?:" + '|'.join(_MODIFIERS) + r")\b", prefix))
    prefix = re.sub(r"\b(?:" + '|'.join(_MODIFIERS) + r")\s*", "", prefix).strip()
    if prefix.startswith('<'):
        end, depth = 0, 0
        for end, character in enumerate(prefix):
            depth += (character == '<') - (character == '>')
            if depth == 0:
                break
        prefix = prefix[end + 1:].strip()
    types = []
    for parameter in _parameters(parameters):
        parameter = re.sub(r"\bfinal\s+", "", parameter.strip())
        named = re.match(r"^(.*?)\s+(" + _IDENTIFIER + r")\s*((?:\[\s*\]\s*)*)$", parameter, re.S)
        if named:
            parameter = named.group(1) + named.group(3)
        types.append(resolve(parameter))
    return name, resolve(prefix), tuple(types), 'static' in modifiers


def _declared_nested_types(code, package):
    """Alias source-declared member types to their canonical names, excluding method-local types."""
    declarations = {match.end() - 1: match.group(1) for match in re.finditer(
        r'\b(?:class|interface|enum|record)\s+(' + _IDENTIFIER + r')\b[^;{}]*\{', code)}
    scopes, aliases, simple_names = [], {}, {}
    for position, character in enumerate(code):
        if character == '{':
            name = declarations.get(position)
            if name and scopes and all(scope is not None for scope in scopes):
                names = [*scopes, name]
                canonical = (package + '.' if package else '') + '.'.join(names)
                binary = (package + '.' if package else '') + '$'.join(names)
                aliases[canonical] = canonical
                aliases[binary] = canonical
                simple_names.setdefault(name, set()).add(canonical)
            scopes.append(name)
        elif character == '}' and scopes:
            scopes.pop()
    for name, candidates in simple_names.items():
        if len(candidates) == 1:
            aliases[name] = next(iter(candidates))
    return aliases


def java_type_resolver(source, known_types=()):
    """Resolve Java source types consistently for methods and constructor contracts."""
    code = _code(source)
    package_match = re.search(r"\bpackage\s+([\w.]+)\s*;", code)
    package = package_match.group(1) if package_match else ''
    nested_types = _declared_nested_types(code, package)
    imports = re.findall(r"\bimport\s+(?!static\b)([\w.]+(?:\*)?)\s*;", code)
    explicit = {name.rsplit('.', 1)[-1]: name for name in imports if not name.endswith('*')}
    wildcards = [name[:-1] for name in imports if name.endswith('*')]

    def resolve(text):
        def token(match):
            name = match.group()
            if name in {'extends', 'super', 'boolean', 'byte', 'char', 'short', 'int', 'long', 'float', 'double', 'void'}:
                return name
            head, separator, tail = name.partition('.')
            if head in explicit:
                expanded = explicit[head] + (separator + tail if separator else '')
                return nested_types.get(expanded, expanded)
            if name in nested_types:
                return nested_types[name]
            if separator and head[0].islower():
                return name
            local = package + '.' + name
            if local in nested_types:
                return nested_types[local]
            if local in known_types:
                return local
            if head in _JAVA_LANG:
                return 'java.lang.' + name
            candidates = [prefix + name for prefix in wildcards if prefix + name in known_types]
            if len(candidates) > 1:
                raise ValueError('Ambiguous Java type in method contract: ' + name)
            if candidates:
                return candidates[0]
            if len(wildcards) == 1:
                return wildcards[0] + name
            return local
        text = _erase_type_arguments(text).replace('...', '[]')
        return re.sub(r"\s+", '', re.sub(_IDENTIFIER + r"(?:\." + _IDENTIFIER + r")*", token, text))

    return resolve


def has_method_contract(source, signature, known_types=()):
    """Check a top-level type's own methods; ignore comments, names and throws spelling."""
    code = _code(source)
    resolve = java_type_resolver(source, known_types)
    expected = _signature(signature, resolve)
    if expected is None:
        return False
    pattern = r"(?:\bpublic\s+|^\s*)([^{};=]*?\([^()]*\))\s*(?:throws\s+[^{};]+)?\s*(?:\{|;)"
    for match in re.finditer(pattern, code, re.M):
        position = match.start()
        prefix = code[:position]
        if prefix.count('{') - prefix.count('}') != 1:
            continue
        declaration = match.group(1)
        if re.match(r"\s*(?:private|protected)\b", declaration):
            continue
        if not re.match(r"\s*public\b", match.group()) and not any(kind == "interface" for kind, _ in public_types(source)):
            continue
        if _signature(declaration, resolve) == expected:
            return True
    return False
