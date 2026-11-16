"""A resolved binary entry is evidence, not framework source to be converted."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class FrameworkBoundaryMethod(BaseModel):
    """Preserve invocation identity without inventing a source body or acceptance proof."""
    model_config = ConfigDict(extra='forbid')
    implementation_class: str
    declaring_class: str
    signature: str
    method: str
    return_type: str
    parameters: list[str]
    jar_path: str
    jar_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    source_required: Literal[False] = False
    conversion_target: Literal[False] = False
