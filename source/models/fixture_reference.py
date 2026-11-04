"""An exact logical value selected from the immutable fixture bank."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FixtureReference(BaseModel):
    """Select an existing fixture and optional RFC6901 pointer; never an expression."""
    model_config = ConfigDict(extra='forbid')
    fixture_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')
    pointer: str = ''

    @field_validator('pointer')
    @classmethod
    def json_pointer(cls, value):
        import re
        if value and not value.startswith('/') or re.search(r'~(?![01])', value):
            raise ValueError('Fixture selector must be an RFC6901 JSON pointer')
        return value

