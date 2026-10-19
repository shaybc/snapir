"""Native ownership determined from compatible behavior-unit consumers."""

from pydantic import BaseModel, Field


class NativeOwnershipPlan(BaseModel):
    """An assignment per compatible whole unit, never per legacy formatter tag."""

    assignments: dict[str, str | None] = Field(default_factory=dict)
    consumers: dict[str, list[str]] = Field(default_factory=dict)
    fingerprint: str
