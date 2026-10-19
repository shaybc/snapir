"""Recognize XML media types expressed as Java literals or Spring constants."""

import re

from runtime.java_public_type import _code
from tools.validation_tools.java_comments import mask_java_comments


def has_xml_media_type(source):
    """Recognize application/xml and resolved Spring MediaType constants without IO."""
    uncommented = mask_java_comments(source)
    if re.search(r'"application/xml(?:\s*;[^"\r\n]*)?"', uncommented):
        return True
    code = _code(source)
    body = re.sub(r'\bimport\s+[^;]+;', '', code)
    constant = r'APPLICATION_XML(?:_VALUE)?\b'
    if re.search(r'\borg\.springframework\.http\.MediaType\s*\.\s*' + constant, body):
        return True
    if re.search(r'\bimport\s+org\.springframework\.http\.(?:MediaType|\*)\s*;', code):
        if re.search(r'\bMediaType\s*\.\s*' + constant, body):
            return True
    # A static import declares the name; require a separate use in executable code.
    imports = re.findall(r'\bimport\s+static\s+org\.springframework\.http\.MediaType\.(APPLICATION_XML(?:_VALUE)?|\*)\s*;', code)
    return any(re.search(r'(?<![\w.])' + (constant if name == '*' else name + r'\b'), body)
               for name in imports)
