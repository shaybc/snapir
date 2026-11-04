"""Declarative typed inputs for the trusted unit harness; no executable bridge code."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NativeBoundaryValue(BaseModel):
    """Bind an XML string, a runtime context value, or an explicitly constructed typed object."""
    model_config = ConfigDict(extra='forbid')
    type_name: str
    source: Literal['xml', 'context', 'object', 'configuration', 'fixture', 'collection', 'item', 'resource']
    key: str | None = None
    arguments: list['NativeBoundaryValue'] = Field(default_factory=list)
    properties: dict[str, 'NativeBoundaryValue'] = Field(default_factory=dict)
    factory_method: str | None = None
    element: 'NativeBoundaryValue | None' = Field(default=None,exclude_if=lambda value:value is None)
