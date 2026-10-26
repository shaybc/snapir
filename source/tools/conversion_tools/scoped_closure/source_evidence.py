"""Select XML occurrences only after verifying the original source bytes."""

import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree


class SourceEvidenceError(ValueError):
    """A selected source definition cannot be verified in the configured workspace."""


class SourceEvidence:
    """Cache only files needed by the current dependency closure, using byte hashes."""

    def __init__(self, composer_root):
        self.root = Path(composer_root).resolve()
        self.documents = {}
        self.used = {}

    def path(self, relative):
        """Resolve a literal source-relative path without permitting workspace escape."""
        path = (self.root / relative).resolve()
        if Path(relative).is_absolute() or '\\' in relative or not path.is_relative_to(self.root):
            raise SourceEvidenceError('Unsafe source-relative path: ' + relative)
        if not path.is_file():
            raise SourceEvidenceError('Source file is missing: ' + relative)
        return path

    def xml(self, reference):
        """Return the exact named XML occurrence described by the imported definition."""
        evidence = reference.evidence
        relative, expected = evidence['source_relative_path'], evidence['source_hash']
        self.used[relative] = expected
        key = (relative, expected)
        if key not in self.documents:
            try:
                raw = self.path(relative).read_bytes()
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise SourceEvidenceError('Source revision differs from intake: ' + relative)
                self.documents[key] = ElementTree.fromstring(raw)
            except (OSError, ElementTree.ParseError) as exc:
                raise SourceEvidenceError(str(exc)) from exc
        node = self.documents[key]
        selector = evidence['source_selector']
        parts = selector.split('/')[1:]
        for index, part in enumerate(parts):
            match = re.fullmatch(r'([^/\[\]]+)\[([1-9][0-9]*)\]', part)
            if not match:
                raise SourceEvidenceError('Unsupported source selector: ' + selector)
            tag, ordinal = match.group(1), int(match.group(2))
            if index == 0:
                if node.tag != tag or ordinal != 1:
                    raise SourceEvidenceError('Source selector root differs: ' + selector)
            else:
                children = [child for child in node if child.tag == tag]
                if ordinal > len(children):
                    raise SourceEvidenceError('Source selector is absent: ' + selector)
                node = children[ordinal - 1]
        if not parts or node.get('id') != reference.entity_id:
            raise SourceEvidenceError('Source definition identity differs: ' + selector)
        return node


def child_selectors(element, selector):
    """Yield children with original per-tag ordinals, before collection filtering."""
    counts = {}
    for child in element:
        counts[child.tag] = counts.get(child.tag, 0) + 1
        yield child, f'{selector}/{child.tag}[{counts[child.tag]}]'
