"""Mask comments, literals and annotations only for Java declaration comparison."""

import re

from runtime.java_public_type import _code


def declaration_text(source):
    """Return a same-length comparison view; original source and annotations stay intact.

    Balanced annotation arguments can contain nested annotations, arrays and calls.
    Comments and literals are masked first so their punctuation cannot change scope.
    Preserve line boundaries for declaration scanning. Malformed annotations fail closed.
    """
    code = ''.join(original if original in '\r\n' else masked
                   for original, masked in zip(source, _code(source)))
    result = list(code)
    pattern = re.compile(r'@([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)')
    position = 0
    while position < len(code):
        match = pattern.match(code, position)
        if not match or match.group(1) == 'interface':
            position += 1
            continue
        end = match.end()
        arguments = end
        while arguments < len(code) and code[arguments].isspace():
            arguments += 1
        if arguments < len(code) and code[arguments] == '(':
            depth, end = 1, arguments + 1
            while end < len(code) and depth:
                depth += (code[end] == '(') - (code[end] == ')')
                end += 1
            if depth:
                raise ValueError('Unbalanced annotation arguments in Java declaration')
        result[position:end] = [character if character in '\r\n' else ' ' for character in code[position:end]]
        position = end
    return ''.join(result)
