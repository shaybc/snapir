"""Structured comparison findings with source and generated-code traceability."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.behavior_fact import BehaviorCitation


class GeneratedBehaviorLocation(BaseModel):
    """Locate the candidate code supporting a comparison finding."""
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class BehaviorFinding(BaseModel):
    """Only concrete observable differences block; stylistic suggestions are advisory."""
    model_config = ConfigDict(extra='forbid')
    fact_id: str | None = None
    status: Literal['matched', 'missing', 'changed', 'invented_behavior',
                    'insufficient_evidence', 'non_behavioral_difference']
    rationale: str = Field(min_length=1)
    trigger: str = ''
    consequence: str = ''
    source_evidence: list[BehaviorCitation] = Field(default_factory=list)
    generated_evidence: list[GeneratedBehaviorLocation] = Field(default_factory=list)


class BehaviorComparison(BaseModel):
    """Review every supplied fact and identify additional source-grounded omissions."""
    model_config = ConfigDict(extra='forbid')
    findings: list[BehaviorFinding] = Field(default_factory=list)
