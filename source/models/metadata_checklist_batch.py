"""Narrow, duplicate-preserving replies for one application-owned checklist batch."""
from typing import Any
from pydantic import BaseModel,ConfigDict,Field


class MetadataChecklistBatch(BaseModel):
    """Validate entries independently after checking the immutable response envelope."""
    model_config=ConfigDict(extra='forbid')
    task_revision:str
    production_revision:str
    batch_id:str
    entries:list[Any]=Field(default_factory=list)
    evidence_requests:list[str]=Field(default_factory=list)


class ComponentSemantics(BaseModel):
    """Only choices/descriptions not already owned by configuration or JavaParser."""
    model_config=ConfigDict(extra='forbid')
    api_types:list[str]=Field(min_length=1)
    api_members:dict[str,list[str]]=Field(default_factory=dict)
    configuration_parameters:dict[str,str]=Field(default_factory=dict)
    runtime_inputs:dict[str,str]=Field(default_factory=dict)
    initialization:list[str]=Field(default_factory=list)
    observable_effects:list[str]=Field(default_factory=list)
    exceptions:list[str]=Field(default_factory=list)


class UnitSemantics(BaseModel):
    """Select exported native owners; the application fills methods and provenance."""
    model_config=ConfigDict(extra='forbid')
    api_types:list[str]=Field(min_length=1)
    api_members:dict[str,list[str]]=Field(default_factory=dict)
