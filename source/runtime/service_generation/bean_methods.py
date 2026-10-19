"""Read Java bean factories without confusing additional annotations with signatures."""

import re

from runtime.java_public_type import _code


def _annotation_end(code, position):
    """Skip one annotation and its balanced arguments; code has masked comments/strings."""
    match = re.match(r'@[\w.$]+\s*', code[position:])
    if not match:
        return position
    end = position + match.end()
    if end < len(code) and code[end] == '(':
        depth = 1
        end += 1
        while end < len(code) and depth:
            depth += (code[end] == '(') - (code[end] == ')')
            end += 1
    return end


def bean_methods(source):
    """Yield return type, method name and bean aliases from executable annotations only."""
    code = _code(source)
    for bean in re.finditer(r'@(?:[\w.$]+\.)?Bean\b', code):
        end = _annotation_end(code, bean.start())
        arguments = source[bean.end():end].strip()
        arguments = arguments[1:-1].strip() if arguments.startswith('(') and arguments.endswith(')') else ''
        aliases = []
        named = re.search(r'\b(?:name|value)\s*=\s*(\{[^}]*\}|"(?:\\.|[^"\\])*")', arguments)
        if named:
            aliases = re.findall(r'"([^"\\]+)"', named[1])
        elif arguments.startswith(('"', '{')):
            aliases = re.findall(r'"([^"\\]+)"', arguments)
        position = end
        while position < len(code):
            position += len(code[position:]) - len(code[position:].lstrip())
            if code[position:position + 1] == '@':
                position = _annotation_end(code, position)
                continue
            modifier = re.match(r'(?:public|protected|private|static|final|synchronized|strictfp|abstract|native|default)\b\s*', code[position:])
            if modifier:
                position += modifier.end()
                continue
            break
        declaration = re.match(r'([\w.$]+(?:\s*<[^;{}()]+>)?(?:\s*\[\])*)\s+([\w$]+)\s*\(', code[position:])
        if declaration:
            yield declaration[1], declaration[2], aliases or [declaration[2]]
