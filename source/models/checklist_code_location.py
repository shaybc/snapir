"""An exact location in the candidate's current production Java sources."""
from pydantic import BaseModel, ConfigDict, Field


class ChecklistCodeLocation(BaseModel):
    """Locations may point anywhere in the generated unit, including shared helpers."""
    model_config = ConfigDict(extra='forbid')
    path: str
    excerpt: str = Field(min_length=1)
