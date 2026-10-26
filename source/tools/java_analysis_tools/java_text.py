"""Decode Java evidence consistently while preserving source bytes on disk."""

from pathlib import Path
import hashlib


def read_java_text(path, *, strip_bom=False, expected_hash=None):
    """Use strict UTF-8, then Windows-1255 only on decode failure; never replace bytes."""
    raw = Path(path).read_bytes()
    if expected_hash is not None and hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError('Java source revision differs from intake: ' + str(path))
    try:
        text = raw.decode('utf-8-sig' if strip_bom else 'utf-8')
    except UnicodeDecodeError:
        text = raw.decode('cp1255')
    return text.replace('\r\n', '\n').replace('\r', '\n')
