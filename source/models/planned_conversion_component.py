"""A source/configuration-bound planning node, never a native acceptance receipt."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PlannedConversionComponent(BaseModel):
    """Separate neutral implementation evidence from configured occurrences and external policies."""
    model_config = ConfigDict(extra='forbid')
    component_id: str
    kind: Literal['java_implementation','external_dependency','unresolved_dependency','configured_step','format_composition','format_node','operation_contract']
    label: str
    status: Literal['source_recorded','external_recorded','unresolved']
    roles: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    dependency_reasons: dict[str,list[str]] = Field(default_factory=dict)
    unit_ids: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    configuration: dict = Field(default_factory=dict)
    source_characters: int = Field(default=0,ge=0)
    issues: list[str] = Field(default_factory=list)

