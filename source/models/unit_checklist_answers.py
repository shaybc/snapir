"""Generation response bound to the source/configuration revision, not an AI approval."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.checklist_response import ChecklistResponse


class UnitChecklistAnswers(BaseModel):
    """The checker computes the candidate hash instead of asking the AI to calculate it."""
    model_config = ConfigDict(extra='forbid')
    unit_id: str
    source_manifest_hash: str
    configuration_hash: str
    responses: list[ChecklistResponse] = Field(default_factory=list)
    schema_version: Literal['unit-checklist-answers-v1'] = 'unit-checklist-answers-v1'
