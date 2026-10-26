"""Locate publicly accessible Java API declarations without treating members as files."""

import re

from runtime.behavior_conversion.java_declaration_text import declaration_text


def public_api_types(source):
    """Map canonical and binary names to type scopes, excluding local/private types.

    Offsets refer to the original source. Every enclosing type must be public;
    interface members are implicitly public unless explicitly private/protected.
    """
    code = declaration_text(source)
    package_match = re.search(r'\bpackage\s+([\w$]+(?:\s*\.\s*[\w$]+)*)\s*;', code)
    package = re.sub(r'\s+', '', package_match.group(1)) if package_match else ''
    pattern = (r'\b((?:(?:public|protected|private|abstract|final|sealed|non-sealed|static|strictfp)\s+)*)'
               r'(@interface|class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b[^;{}]*\{')
    declarations = {match.end() - 1: match for match in re.finditer(pattern, code)}
    scopes, result = [], {}
    for position, character in enumerate(code):
        if character == '{':
            match = declarations.get(position)
            item = None
            if match and all(scope is not None for scope in scopes):
                modifiers, kind, name = match.groups()
                visibility = set(modifiers.split())
                parent = scopes[-1] if scopes else None
                accessible = not visibility.intersection({'private', 'protected'}) and (
                    'public' in visibility or parent is not None and parent['kind'] in {'interface', '@interface'})
                accessible = accessible and all(scope['public'] for scope in scopes)
                names = [scope['name'] for scope in scopes] + [name]
                item = dict(name=name, kind=kind, public=accessible, body_start=position,
                            canonical=(package + '.' if package else '') + '.'.join(names),
                            binary=(package + '.' if package else '') + '$'.join(names))
            scopes.append(item)
        elif character == '}' and scopes:
            item = scopes.pop()
            if item and item['public']:
                item['body_end'] = position
                result[item['canonical']] = item
                result[item['binary']] = item
    return result
