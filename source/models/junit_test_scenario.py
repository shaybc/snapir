"""Small native-unit scenarios referencing shared logical data."""
from pydantic import BaseModel, ConfigDict, Field
from models.fixture_reference import FixtureReference
from models.native_verification_binding import NativeVerificationBinding
from models.format_context_requirement import FormatSourceCitation
from typing import Literal
from models.native_test_setup import NativeTestSetup


class JunitTestScenario(BaseModel):
    """AI chooses a native entry and assertions; generated JUnit executes this scenario."""
    model_config = ConfigDict(extra='forbid')
    scenario_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$')
    purpose: str = Field(min_length=1)
    native_entry: NativeVerificationBinding
    setup: list[NativeTestSetup] = Field(default_factory=list)
    entry_kind: Literal['method','constructor'] = 'method'
    inputs: dict[str, FixtureReference] = Field(default_factory=dict)
    configuration: dict[str, FixtureReference] = Field(default_factory=dict)
    input_xml: FixtureReference | None = None
    resources: dict[str, FixtureReference] = Field(default_factory=dict)
    assertions: list[str] = Field(min_length=1)
    assertion_citations: list[FormatSourceCitation] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class JunitScenarioSuite(BaseModel):
    """Independent JUnit suite, not a list of whole-boundary comparisons."""
    model_config = ConfigDict(extra='forbid')
    scenarios: list[JunitTestScenario] = Field(min_length=1)
    unresolved: list[str] = Field(default_factory=list)

