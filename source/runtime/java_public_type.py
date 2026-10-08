"""Identify a converted source file's public top-level Java type and native package."""

import re

import constants


def _code(source):
    """Mask comments and literals so their braces and declarations are ignored."""
    pattern = r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*'
    return re.sub(pattern, lambda match: " " * len(match.group()), source)


def public_types(source):
    """Find public declarations at brace depth zero, including all supported Java type kinds."""
    code = _code(source)
    pattern = r'\b((?:(?:public|abstract|final|sealed|non-sealed|static|strictfp)\s+)*)(@interface|class|interface|enum|record)\s+([A-Za-z_$][\w$]*)'
    result = []
    for match in re.finditer(pattern, code):
        prefix = code[:match.start()]
        if "public" in match.group(1).split() and prefix.count("{") == prefix.count("}"):
            result.append((match.group(2), match.group(3)))
    return result


def converted_java_identity(source, original_source=None):
    """Require one native public type and preserve the original Java type category."""
    declarations = public_types(source)
    if len(declarations) != 1:
        raise ValueError("Conversion must return exactly one public top-level Java type "
                         "(class, interface, enum, record, or annotation type).")
    code = _code(source)
    package = re.search(r'\bpackage\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;', code)
    name = package.group(1) if package else ""
    if name != constants.JAVA_PACKAGE_BASE and not name.startswith(constants.JAVA_PACKAGE_BASE + "."):
        raise ValueError(f"Conversion returned package '{name or '(default package)'}'. "
                         f"Use the native destination package {constants.JAVA_PACKAGE_BASE} or its subpackages; "
                         "legacy IBM packages must be replaced before compilation.")
    if original_source:
        original = public_types(original_source)
        if len(original) == 1 and original[0][0] != declarations[0][0]:
            raise ValueError(f"Conversion changed the original public {original[0][0]} into a "
                             f"{declarations[0][0]}; preserve its Java type category and behavior.")
    return name, declarations[0][1]
