"""Reproducible unit-boundary inputs and controlled environment values."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class BoundaryCase(BaseModel):
    """Use the same input, clock, seed, settings and replay responses on both sides."""
    model_config = ConfigDict(extra='forbid')
    case_id: str
    input_xml: str | None = None
    initial_context: dict[str, Any] = Field(default_factory=dict)
    clock_millis: int = 1704153600000
    random_seed: int = 1729
    settings: list[dict[str, Any]] = Field(default_factory=list)
    external_responses: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

