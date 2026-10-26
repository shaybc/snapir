"""A selected step occurrence in an operation execution context."""

from dataclasses import dataclass
from models.scoped_entity_reference import ScopedEntityReference


@dataclass(frozen=True)
class ScopedStepOccurrence:
    """Retain zero-based source and effective positions without using labels as keys."""

    operation_identity: str
    source_index: int
    effective_index: int
    source: ScopedEntityReference
    transition_targets: dict
    calls: tuple[dict, ...]
