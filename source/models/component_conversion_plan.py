"""CF1 planning metadata kept separate from existing configured units and routing."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.planned_conversion_component import PlannedConversionComponent
from models.component_conversion_group import ComponentConversionGroup


class ComponentConversionPlan(BaseModel):
    """Describe dependencies and limitations without enabling generation or acceptance."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['component-plan-v1'] = 'component-plan-v1'
    status: Literal['planned','incomplete'] = 'planned'
    generation_enabled: Literal[False] = False
    acceptance_gate_enabled: Literal[False] = False
    dependency_scope: Literal['recorded_qualified_java_syntax_and_effective_configuration'] = 'recorded_qualified_java_syntax_and_effective_configuration'
    method_path_analysis: Literal['not_recomputed'] = 'not_recomputed'
    components: dict[str,PlannedConversionComponent] = Field(default_factory=dict)
    unit_roots: dict[str,str] = Field(default_factory=dict)
    groups: list[ComponentConversionGroup] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    fingerprint: str = ''

