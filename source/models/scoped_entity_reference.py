"""Qualified canonical source evidence, independent of consuming-channel execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopedEntityReference:
    """Identify a source definition and retain its literal vault-relative path."""

    definition_id: str
    usage_id: str
    kind: str
    entity_id: str
    note: str
    evidence: dict
