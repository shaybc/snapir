"""Declarative native entry metadata, never generated implementation or harness code."""
from pydantic import BaseModel, ConfigDict
from models.native_verification_binding import NativeVerificationBinding


class ComponentUnitBinding(BaseModel):
    """Describe the frozen component API used by the whole-unit comparison adapter."""
    model_config = ConfigDict(extra='forbid')
    verification_binding: NativeVerificationBinding
    input_type: str | None = None
    output_type: str | None = None
    wire_type: str | None = None
