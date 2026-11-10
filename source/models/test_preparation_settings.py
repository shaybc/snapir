"""Explicit preparation policy for shared AI fixtures and independent test suites."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field,model_validator


class TestPreparationSettings(BaseModel):
    """Opt in without changing the existing deterministic preparation path."""
    model_config = ConfigDict(extra='forbid')
    mode: Literal['existing', 'ai_shared_fixtures_v1'] = 'existing'
    request_chars: int = Field(default=2700000, ge=1000, le=2700000)
    response_chars: int = Field(default=16000,ge=1000,le=200000)
    max_fixture_bytes: int = Field(default=2000000, ge=1024, le=10000000)
    max_junit_scenarios: int = Field(default=128, ge=1, le=512)

    @model_validator(mode='after')
    def response_reserve(self):
        if self.response_chars>=self.request_chars:raise ValueError('Test preparation response reserve must be smaller than the request budget')
        return self

