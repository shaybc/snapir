"""Configured behavior evidence supplied to one native conversion task."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SourceEvidence(BaseModel):
    """An immutable source excerpt with identity and content hash."""

    model_config = ConfigDict(extra="forbid")
    identity: str
    content: str
    content_hash: str


class BehaviorUnitInput(BaseModel):
    """A complete format direction or configured step, independent of output classes."""

    model_config = ConfigDict(extra="forbid")
    unit_id: str
    kind: Literal["request_unformat", "response_format", "configured_step"]
    logical_id: str
    configuration_xml: str
    sources: list[SourceEvidence] = Field(default_factory=list)
    consumers: list[str] = Field(default_factory=list)
    external_dependencies: list[dict] = Field(default_factory=list)
    referenced_definitions: list[dict] = Field(default_factory=list)
    service_connections: list[dict] = Field(default_factory=list, exclude_if=lambda value: not value)
    operation_calls: list[dict] = Field(default_factory=list, exclude_if=lambda value: not value)
    fingerprint: str
    schema_version: str = "v1"
