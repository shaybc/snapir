"""Qualified dependency evidence kept separate from conversion-ready legacy closures."""

from typing import Literal
from pydantic import Field
from models.common_models.common import SnapirBaseModel
from models.conversion_models import ClosureBlockingIssue
from models.scoped_step_occurrence import ScopedStepOccurrence
from models.scoped_format_node import ScopedFormatNode


class ScopedOperationClosure(SnapirBaseModel):
    """Describe one consuming context; evidence readiness never enables generation."""

    run_id: str
    operation_identity: str
    operation_id: str
    channel: str
    definition_id: str
    status: Literal['evidence_ready', 'blocked'] = 'blocked'
    conversion_enabled: Literal[False] = Field(default=False, frozen=True)
    operation: dict = Field(default_factory=dict)
    source_revisions: dict[str, str] = Field(default_factory=dict)
    entry_step_note: str = ''
    steps: list[ScopedStepOccurrence] = Field(default_factory=list)
    routing_graph: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    return_body_switches: dict[str, dict[str, str]] = Field(default_factory=dict)
    format_roles: dict[str, str] = Field(default_factory=dict)
    formats: dict[str, ScopedFormatNode] = Field(default_factory=dict)
    context_chain: list[dict] = Field(default_factory=list)
    context_fields: list[dict] = Field(default_factory=list)
    java_origins: list[dict] = Field(default_factory=list)
    external_dependencies: list[dict] = Field(default_factory=list)
    composer_behavior_evidence: list[dict] = Field(default_factory=list)
    calls: list[dict] = Field(default_factory=list)
    dependency_contexts: list[str] = Field(default_factory=list)
    blocking_issues: list[ClosureBlockingIssue] = Field(default_factory=list)
    evidence_hash: str = ''
