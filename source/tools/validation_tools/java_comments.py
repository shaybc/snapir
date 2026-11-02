"""Mask Java comments while preserving executable code, literals and line numbers."""

import re

_TOKENS = re.compile(
    r'(?P<literal>"""(?:\\[\s\S]|(?!""")[\s\S])*"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r'|(?P<comment>/\*[\s\S]*?\*/|//[^\r\n]*)'
)


def mask_java_comments(source):
    """Replace comments with whitespace; keep strings, text blocks and chars intact."""
    def replace(match):
        if match.group('comment') is None:
            return match.group()
        return ''.join(character if character in '\r\n' else ' ' for character in match.group())
    return _TOKENS.sub(replace, source)


def mask_java_non_code(source):
    """Mask comments and literals, preserving offsets and newlines for dependency diagnostics."""
    return _TOKENS.sub(lambda match: ''.join(character if character in '\r\n' else ' '
        for character in match.group()), source)
