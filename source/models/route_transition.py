"""An original configured operation edge a scenario must exercise."""

from pydantic import BaseModel, ConfigDict, Field


class RouteTransition(BaseModel):
    """Identify a branch by its source step, configured outcome and destination."""

    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    target: str = Field(min_length=1)
