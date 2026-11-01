"""Trusted persisted human exceptions, supplied separately from generation answers."""
from pydantic import BaseModel, ConfigDict, Field


class ChecklistExclusionAuthorization(BaseModel):
    """A changed source, configuration or candidate invalidates this exact-item authorization."""
    model_config = ConfigDict(extra='forbid')
    approval_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: str = Field(min_length=1)
    unit_id: str
    source_manifest_hash: str
    configuration_hash: str
    candidate_hash: str
    checklist_id: str
    rationale: str = Field(min_length=1)
