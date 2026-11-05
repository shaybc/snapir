"""Explicit whole-operation links into immutable existing fixture banks."""
from pydantic import BaseModel, ConfigDict, Field
from models.fixture_demo_catalogue import FixtureDatabaseReference


class DemoValueLink(BaseModel):
    """Two saved values that an operation scenario explicitly declares connected."""
    model_config = ConfigDict(extra='forbid')
    producer: FixtureDatabaseReference
    consumer: FixtureDatabaseReference


class OperationDemoScenario(BaseModel):
    """A complete request and named database resources, never a guessed component join."""
    model_config = ConfigDict(extra='forbid')
    scenario_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')
    input_xml: FixtureDatabaseReference
    resources: dict[str, list[FixtureDatabaseReference]] = Field(min_length=1)
    links: list[DemoValueLink] = Field(default_factory=list)
    expected_xml: FixtureDatabaseReference | None = None
    expected_resource_executions: int | None = Field(default=None,ge=0,le=10000)


class OperationDemoScenarios(BaseModel):
    """Saved, operation-scoped preparation evidence; fixture payloads remain in their banks."""
    model_config = ConfigDict(extra='forbid')
    schema_version: str = Field(default='operation-demo-scenarios-v1', pattern=r'^operation-demo-scenarios-v1$')
    operation: str
    selected_scenario: str | None = None
    scenarios: list[OperationDemoScenario] = Field(min_length=1, max_length=64)
