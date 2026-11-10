"""Source-backed original format invocation contracts, independent of native API structure."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class FormatInvocation(BaseModel):
    """One original receiver method; parameter names identify exact runtime types."""
    model_config = ConfigDict(extra='forbid')
    method: str
    declaring_class: str
    signature: str
    returns: str
    parameters: list[str] = Field(default_factory=list)
    source_identity: str
    source_hash: str


class FormatOrderingEvidence(BaseModel):
    """Original caller location establishing an ordered lifecycle sequence."""
    model_config = ConfigDict(extra='forbid')
    source_identity: str
    source_hash: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class FormatLifecycle(BaseModel):
    """Ordered original calls established from source, never a required native hierarchy."""
    model_config = ConfigDict(extra='forbid')
    version: Literal['format-lifecycle-v1'] = 'format-lifecycle-v1'
    direction: Literal['format', 'unformat']
    invocations: list[FormatInvocation] = Field(min_length=1)
    ordering_evidence: list[FormatOrderingEvidence] = Field(default_factory=list)
