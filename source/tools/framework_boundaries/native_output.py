"""Prevent original framework binaries and class identities leaking into native output."""
import re
from tools.framework_boundaries.inventory import current


def reject_framework_output(files):
    """Check real Java tokens, not comments/literals, against exact configured binary classes."""
    classes = {name.replace('$', '.') for name in current()}
    if not classes: return
    from runtime.java_public_type import _code
    from runtime.behavior_conversion.java_api_types import public_api_types
    for file in files:
        if not file.path.startswith('src/main/java/'): continue
        if set(public_api_types(file.content)) & classes:
            raise ValueError('Native output cannot recreate original framework classes: ' + file.path)
        code = _code(file.content)
        for match in re.finditer(r'\b[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)+', code):
            name = re.sub(r'\s+', '', match.group())
            while '.' in name:
                if name in classes:
                    raise ValueError('Native output cannot depend on original framework class: ' + name)
                name = name.rsplit('.', 1)[0]
        for match in re.finditer(r'\bimport\s+([\w.$]+)\.\*\s*;', code):
            package = match[1]
            for name in classes:
                if name.rsplit('.', 1)[0] == package and re.search(r'\b' + re.escape(name.rsplit('.', 1)[1]) + r'\b', code):
                    raise ValueError('Native output cannot depend on original framework class: ' + name)
