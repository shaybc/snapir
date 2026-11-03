"""Source-backed runtime inputs and branch values, without generated expectations."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FormatSourceCitation(BaseModel):
    """An exact excerpt from an identified original source or configuration document."""
    model_config = ConfigDict(extra='forbid')
    source_identity: str
    excerpt: str = Field(min_length=1)


class FormatContextValue(BaseModel):
    """One proposed input, explicitly distinguishing evidence from exploration."""
    model_config = ConfigDict(extra='forbid')
    value: Any
    origin: Literal['source_backed', 'exploratory']
    citations: list[FormatSourceCitation] = Field(default_factory=list)
    branch_id: str | None = None
    branch_outcome: str | None = None


class FormatContextRequirement(BaseModel):
    """A context read discovered from original code, not an adapter implementation."""
    model_config = ConfigDict(extra='forbid')
    requirement_id: str
    directions: list[Literal['format', 'unformat']] | None = None
    context_key: str | None = None
    key_expression: str | None = None
    value_type: Literal['string', 'boolean', 'integer', 'number', 'list', 'map', 'unknown'] = 'unknown'
    required: bool = True
    condition: str = ''
    presence_behavior: str = ''
    citations: list[FormatSourceCitation] = Field(min_length=1)
    values: list[FormatContextValue] = Field(default_factory=list)
    unresolved_reason: str | None = None

    @model_validator(mode='after')
    def unresolved_dynamic_path(self):
        if self.context_key is None and not self.unresolved_reason:
            raise ValueError('A dynamic/unresolved path needs an explicit unresolved reason')
        return self


class FormatContextDiscovery(BaseModel):
    """Nonexhaustive discovery inventory retained alongside all execution reports."""
    model_config = ConfigDict(extra='forbid')
    requirements: list[FormatContextRequirement] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: ['AI discovery is not proof that every context read or branch was found'])

