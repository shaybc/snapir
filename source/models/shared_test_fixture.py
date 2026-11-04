"""Reusable logical data; runtime objects and business outcomes are not fixture code."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from models.format_context_requirement import FormatSourceCitation


class SharedTestFixture(BaseModel):
    """One synthetic value, XML document, dataset or external-response sequence."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    kind: Literal['value', 'xml', 'context', 'database', 'service'] = 'value'
    value: JsonValue
    origin: Literal['source_backed', 'exploratory', 'regression'] = 'exploratory'
    citations: list[FormatSourceCitation] = Field(default_factory=list)


class SharedFixtureBank(BaseModel):
    """Versioned fixtures shared by independently defined JUnit and comparison scenarios."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['shared-fixtures-v1'] = 'shared-fixtures-v1'
    fixtures: dict[str, SharedTestFixture] = Field(min_length=1)
    unresolved: list[str] = Field(default_factory=list)

