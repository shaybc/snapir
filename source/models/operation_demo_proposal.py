"""AI preparation output references existing banks or one append-only new fixture bank."""
from pydantic import BaseModel,ConfigDict,Field
from models.fixture_reference import FixtureReference
from models.shared_test_fixture import SharedTestFixture
from models.format_context_requirement import FormatSourceCitation


class ScenarioFixtureSelection(FixtureReference):
    """Bank is a supplied manifest hash or the literal 'generated'; no guessed disk paths."""
    bank: str = Field(pattern=r'^(generated|[a-f0-9]{64})$')


class ScenarioValueLink(BaseModel):
    """Explicit connections between saved logical values, with storage shape left unchanged."""
    model_config=ConfigDict(extra='forbid')
    producer: ScenarioFixtureSelection
    consumer: ScenarioFixtureSelection


class ProposedOperationScenario(BaseModel):
    """A complete XML/JDBC scenario, including a pre-execution expected response."""
    model_config=ConfigDict(extra='forbid')
    scenario_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')
    purpose: str = Field(min_length=1)
    input_xml: ScenarioFixtureSelection
    expected_xml: ScenarioFixtureSelection
    resources: dict[str,list[ScenarioFixtureSelection]] = Field(min_length=1)
    links: list[ScenarioValueLink] = Field(default_factory=list)
    expected_resource_executions: int = Field(ge=1,le=10000)
    expectation_citations: list[FormatSourceCitation] = Field(min_length=1)


class OperationDemoProposal(BaseModel):
    """Fixture preparation only; it cannot return Java, modify saved banks or select a live endpoint."""
    model_config=ConfigDict(extra='forbid')
    operation: str
    selected_scenario: str | None = None
    new_fixtures: dict[str,SharedTestFixture] = Field(default_factory=dict)
    scenarios: list[ProposedOperationScenario] = Field(default_factory=list,max_length=64)
    unresolved: list[str] = Field(default_factory=list)
