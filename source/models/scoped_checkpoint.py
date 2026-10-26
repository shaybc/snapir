"""Evidence required before reusing one consuming context's prepared work."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ScopedCheckpoint(BaseModel):
    """Bind a context to immutable inputs without accepting native generation."""

    model_config = ConfigDict(extra='forbid')
    operation_identity: str
    operation_key: str
    fingerprint: str
    inputs: dict
    dependencies: list[str] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)
    status: Literal['current', 'stale'] = 'current'
