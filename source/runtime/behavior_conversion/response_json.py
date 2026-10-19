"""Normalize escaped JSON structure without rewriting Java source strings."""

import json

JSON_INSTRUCTION = """Return actual JSON syntax, not JSON encoded inside JSON. dependencies must be an array of objects with quoted keys. Use real whitespace between JSON tokens; never write literal backslash-n or escaped quote delimiters outside JSON strings. Escape newlines and quotes only inside string values such as Java source. Before returning every response (initial or correction), check the entire response for valid JSON syntax and verify it against schema."""


def clean_structural_escapes(response):
    """Decode only escaped structural lines, then normalize whitespace outside strings."""
    lines = []
    for line in response.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(r'{\n') and r'\"' in stripped:
            try:
                decoded = json.loads('"' + stripped + '"')
                line = line[:len(line) - len(line.lstrip())] + decoded + '\n'
            except json.JSONDecodeError:
                pass
        lines.append(line)
    text = ''.join(lines)
    result, inside, escaped, index = [], False, False, 0
    while index < len(text):
        character = text[index]
        if inside:
            result.append(character)
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                inside = False
        elif character == '"':
            inside = True
            result.append(character)
        elif character == '\\' and index + 1 < len(text) and text[index + 1] in 'nrt':
            result.append({'n': '\n', 'r': '\r', 't': '\t'}[text[index + 1]])
            index += 1
        else:
            result.append(character)
        index += 1
    return ''.join(result)
