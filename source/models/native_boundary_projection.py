"""Describe an observable value read from the actual native result or typed argument."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NativeBoundaryProjection(BaseModel):
    """Only public zero-argument getters are traversed; no fabricated expected values."""
    model_config = ConfigDict(extra='forbid')
    context_key: str
    source: Literal['result', 'argument', 'receiver'] = 'result'
    argument_index: int = Field(default=0, ge=0)
    getters: list[str] = Field(default_factory=list)
    presence_getters: list[str] = Field(default_factory=list)
    collection_fields: dict[str, list[str]] = Field(default_factory=dict)
    collection_fields: dict[str, list[str]] = Field(default_factory=dict)
