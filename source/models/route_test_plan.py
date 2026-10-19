"""Persist a checked test plan before generating individual operation scenarios."""

from pydantic import BaseModel, ConfigDict, Field
from models.route_test_scenario import RouteTestScenario


class RouteTestPlan(BaseModel):
    """Plan route tests against original routing and the provisional assembled service."""

    model_config = ConfigDict(extra="forbid")
    scenarios: list[RouteTestScenario] = Field(min_length=1)
    unresolved_questions: list[str] = Field(default_factory=list)
