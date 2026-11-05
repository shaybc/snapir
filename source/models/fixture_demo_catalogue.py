"""Reference-only fixture JDBC catalogue shared with future operation demo preparation."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from models.fixture_reference import FixtureReference


class FixtureDatabaseReference(FixtureReference):
    """An existing immutable bank revision, fixture identity, and strict JSON pointer."""
    asset_root: str = Field(min_length=1)
    manifest_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


class FixtureDatabaseResource(BaseModel):
    """References merged in memory; no database response payload is copied here."""
    model_config = ConfigDict(extra='forbid')
    fixtures: list[FixtureDatabaseReference] = Field(min_length=1)


class FixtureDatabaseScenario(BaseModel):
    """Named JDBC resources that share one externally selected scenario."""
    model_config = ConfigDict(extra='forbid')
    resources: dict[str, FixtureDatabaseResource] = Field(min_length=1)

    @field_validator('resources')
    @classmethod
    def resource_ids(cls, value):
        import re
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', key) for key in value):
            raise ValueError('Invalid fixture resource ID')
        return value


class FixtureDemoCatalogue(BaseModel):
    """A frozen source of fixture references; no code or method selection is accepted."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['fixture-jdbc-catalogue-v1'] = 'fixture-jdbc-catalogue-v1'
    scenarios: dict[str, FixtureDatabaseScenario] = Field(min_length=1, max_length=1024)

    @field_validator('scenarios')
    @classmethod
    def scenario_ids(cls, value):
        return FixtureDatabaseScenario.resource_ids(value)
