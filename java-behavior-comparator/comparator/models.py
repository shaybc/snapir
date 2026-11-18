"""JSON protocol identities and comparison outcomes; no equivalence-proof status exists."""
import hashlib
import json
from pathlib import Path

SCHEMA = 'java-behavior-comparison-v1'
VERSION = '1.0.0'
DECISIONS = {'consistent_in_review': 0, 'differences_found': 1, 'inconclusive': 2, 'error': 3}


def digest(value):
    """Hash canonical JSON for cache and evidence identities."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    """Hash exact input bytes, independently of source encoding."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    """Atomically write a comparator-owned UTF-8 JSON record."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


class Incomplete(Exception):
    """A bounded analysis task cannot be completed with the available evidence or budget."""
