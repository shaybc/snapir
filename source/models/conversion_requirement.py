"""Versioned behavior obligations independent of conversion-prompt wording."""

from pydantic import BaseModel, ConfigDict, Field


class ConversionRequirement(BaseModel):
    """Declare an obligation and the unit kinds or task categories it applies to.

    Increment version when required behavior changes; descriptions may be clarified
    without a bump. applies_to accepts unit kinds, task categories, or "*".
    """

    model_config = ConfigDict(extra="forbid")
    requirement_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str = Field(min_length=1)
    applies_to: list[str] = Field(default_factory=lambda: ["*"], min_length=1)
