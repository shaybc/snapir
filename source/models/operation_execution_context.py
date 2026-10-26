"""A mapped operation executed with one consuming channel's bindings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationExecutionContext:
    """Keep contextual identity separate from the canonical source operation."""

    run_id: str
    operation_identity: str
    channel: str
    operation_id: str
    definition_id: str
    note: str
    evidence: dict
