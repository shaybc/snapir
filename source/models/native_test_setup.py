"""Explicit native static configuration with source-owned public restoration accessors."""
from pydantic import BaseModel,ConfigDict,Field
from models.native_boundary_value import NativeBoundaryValue


class NativeTestSetup(BaseModel):
    """Configure actual native settings and restore the values read before the case."""
    model_config=ConfigDict(extra='forbid')
    owner_type:str
    method_name:str
    arguments:list[NativeBoundaryValue]=Field(min_length=1)
    restore_getters:list[str]=Field(min_length=1)
