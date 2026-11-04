"""Complete format or configured-step scenarios with paired input mappings."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.fixture_reference import FixtureReference
from models.native_verification_binding import NativeVerificationBinding


class ComparisonTestScenario(BaseModel):
    """Both sides use identical logical fixtures and independent runtime instances."""
    model_config = ConfigDict(extra='forbid')
    scenario_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$')
    purpose: str = Field(min_length=1)
    direction: Literal['format', 'unformat', 'step_execute']
    native_entry: NativeVerificationBinding
    inputs: dict[str, FixtureReference] = Field(default_factory=dict)
    composer_context: dict[str, FixtureReference] = Field(default_factory=dict)
    input_xml: FixtureReference | None = None
    resources: dict[str, FixtureReference] = Field(default_factory=dict)
    composer_resource_setters: dict[str, str] = Field(default_factory=dict)
    external_responses: FixtureReference | None = None
    settings: FixtureReference | None = None
    clock_millis: int = 1704153600000
    random_seed: int = 1729
    observe_context_keys: list[str] | None = None
    unresolved: list[str] = Field(default_factory=list)


class ComparisonScenarioSuite(BaseModel):
    """AI explicitly selects every case; no automatic cross-product expansion."""
    model_config = ConfigDict(extra='forbid')
    scenarios: list[ComparisonTestScenario] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    legacy_external_bindings: dict[str,str] = Field(default_factory=dict)
    native_external_bindings: dict[str,str] = Field(default_factory=dict)

