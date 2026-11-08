"""Describe automatic dependency work separately from the user's requested outputs."""
from pydantic import BaseModel, ConfigDict, Field


class DependencyResolutionPlan(BaseModel):
    """Retain qualified identities, reuse choices and the evidence path for required work."""
    model_config = ConfigDict(extra='forbid')
    schema_version: str = 'automatic-dependencies-v1'
    requested_operations: list[str] = Field(default_factory=list)
    required_operations: list[str] = Field(default_factory=list)
    source_operations: list[str] = Field(default_factory=list)
    operation_paths: dict[str, list[str]] = Field(default_factory=dict)
    reused_services: dict[str, dict] = Field(default_factory=dict)
    source_projects: dict[str, str | None] = Field(default_factory=dict)
    components: dict[str, dict] = Field(default_factory=dict)
    order: list[str] = Field(default_factory=list)
    blockers: list[dict] = Field(default_factory=list)
