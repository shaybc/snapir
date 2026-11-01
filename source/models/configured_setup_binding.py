"""Preserve each configured implementation occurrence and its setup attributes."""

from pydantic import BaseModel, ConfigDict, Field


class ConfiguredSetupBinding(BaseModel):
    """Attribute-to-setter candidates are evidence, not an assertion that a setter executes."""

    model_config = ConfigDict(extra='forbid')

    implementation_class: str
    occurrence_id: str | None = None
    source_selector: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
