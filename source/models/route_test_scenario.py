"""One evidence-backed operation test to generate and validate independently."""

from pydantic import BaseModel, ConfigDict, Field
from models.route_transition import RouteTransition


class RouteTestScenario(BaseModel):
    """Define inputs, collaborator setup and observable outcomes for one route case."""

    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    description: str = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    dependency_setup: list[str] = Field(default_factory=list)
    expected_outcome: str = Field(min_length=1)
    expected_side_effects: list[str] = Field(default_factory=list)
    covers: list[str] = Field(min_length=1)
    routes: list[RouteTransition] = Field(default_factory=list)
