"""Native public entry metadata consumed by a converter-owned comparison adapter."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from models.native_boundary_value import NativeBoundaryValue
from models.native_boundary_projection import NativeBoundaryProjection
from models.native_settings_binding import NativeSettingsBinding


class NativeVerificationBinding(BaseModel):
    """The AI describes API wiring, never source code implementing the verification bridge."""
    model_config = ConfigDict(extra='forbid')
    owner_type: str
    method_name: str
    static_method: bool = False
    constructor_arguments: list[NativeBoundaryValue] = Field(default_factory=list)
    arguments: list[NativeBoundaryValue] = Field(default_factory=list)
    configuration_setters: dict[str, NativeBoundaryValue] = Field(default_factory=dict)
    context_writes: list[NativeBoundaryProjection] = Field(default_factory=list)
    output: Literal['none', 'result'] = 'result'
    output_getters: list[str] = Field(default_factory=list)
    settings_bindings: dict[str, NativeSettingsBinding] = Field(default_factory=dict)
