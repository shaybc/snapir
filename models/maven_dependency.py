"""Validated dependency proposals returned with converted Java code."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MavenDependency(BaseModel):
    """Identify a pinned Maven artifact and the APIs that justify its inclusion."""

    model_config = ConfigDict(extra="forbid")
    group_id: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    artifact_id: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    version: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    scope: Literal["compile", "runtime", "provided", "test"] = "compile"
    reason: str = Field(min_length=1)
    required_classes: list[str] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def require_pinned_version(cls, value):
        """Reject dynamic or snapshot versions for generated dependencies."""
        if value.upper() in {"LATEST", "RELEASE"} or value.upper().endswith("-SNAPSHOT"):
            raise ValueError("Dependency versions must be pinned releases")
        return value

    @property
    def coordinates(self) -> str:
        """Return the immutable artifact identity used for approval."""
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


class JavaConversionOutput(BaseModel):
    """Carry transient proposals to the POM owner alongside converted source."""

    model_config = ConfigDict(extra="forbid")
    java_source: str = Field(min_length=1)
    dependencies: list[MavenDependency] = Field(default_factory=list)
