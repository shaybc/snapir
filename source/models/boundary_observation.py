"""One isolated JVM execution, including state left behind on failure."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class BoundaryObservation(BaseModel):
    """Capture observable effects; inability to capture them remains incomplete."""
    model_config = ConfigDict(extra='forbid')
    case_id: str
    status: Literal['completed', 'verification_incomplete']
    invocation_completed: bool | None = None
    failure_origin: Literal['adapter_binding'] | None = None
    output: Any = None
    context: dict[str, Any] = Field(default_factory=dict)
    writes: list[dict[str, Any]] = Field(default_factory=list)
    removals: list[dict[str, Any]] = Field(default_factory=list)
    external_calls: list[dict[str, Any]] = Field(default_factory=list)
    exception: dict[str, Any] | None = None
    probes: list[dict[str, str]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

