"""Expose compact verified Java declarations instead of guessing accepted APIs."""

import re
from runtime.java_public_type import _code


def api_surface(bundle):
    """Retain imports, type headers and public members, excluding method bodies."""
    result = {}
    for item in bundle.files:
        if not item.path.startswith("src/main/java/"):
            continue
        code = _code(item.content)
        depth, depths = 0, []
        for char in code:
            depths.append(depth)
            depth += (char == "{") - (char == "}")
        declarations = []
        for match in re.finditer(r"\bpublic\s+[^;{}]*[;{]", code):
            if depths[match.start()] in {0, 1}:
                declarations.append(item.content[match.start():match.end()].rstrip("{;").strip())
        imports = [match.group().strip() for match in re.finditer(r"\bimport\s+[^;]+;", code)]
        result[item.path] = dict(imports=imports, public_declarations=declarations)
    return result
