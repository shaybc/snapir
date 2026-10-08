"""Declare unavailable library source and its intended migration treatment."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExternalDependencyRule(BaseModel):
    """Match an exact class or a package boundary and retain or replace its behavior."""
    model_config = ConfigDict(extra="forbid")
    class_name: str | None = None
    package_prefix: str | None = None
    treatment: Literal["retain", "replace"]
    maven_coordinates: str | None = None
    behavior_sections: list[str] = Field(default_factory=list, exclude=True)
    behavior_description: str = ""

    @model_validator(mode="after")
    def validate_selector(self):
        """Require one explicit selector while accepting older saved evidence fields."""
        if bool(self.class_name) == bool(self.package_prefix):
            raise ValueError("Specify exactly one class_name or package_prefix")
        return self
