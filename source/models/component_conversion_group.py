"""An indivisible dependency group in the proposed component conversion order."""
from pydantic import BaseModel, ConfigDict, Field


class ComponentConversionGroup(BaseModel):
    """Cycles remain coordinated groups; unresolved prerequisites never look schedulable."""
    model_config = ConfigDict(extra='forbid')
    group_id: str
    members: list[str]
    dependencies: list[str] = Field(default_factory=list)
    wave: int | None = None
    cyclic: bool = False
    reason: str

