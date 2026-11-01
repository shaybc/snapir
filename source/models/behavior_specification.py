"""Persistable behavior extraction results and cross-part uncertainty reports."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.behavior_fact import BehaviorFact


class BehaviorSpecification(BaseModel):
    """Keep source obligations separate from uncertain or missing evidence."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['source-behavior-v1'] = 'source-behavior-v1'
    facts: list[BehaviorFact] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class BehaviorReconciliation(BaseModel):
    """Report cross-part conflicts without deleting extracted facts."""
    model_config = ConfigDict(extra='forbid')
    conflicting_fact_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
