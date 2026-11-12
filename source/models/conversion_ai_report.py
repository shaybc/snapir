"""Saved evidence describing AI activity without claiming unobserved delivery or acceptance."""
from pydantic import BaseModel, ConfigDict, Field


class ConversionAiReport(BaseModel):
    """One observed run, with target histories and explicit evidence limitations."""
    model_config = ConfigDict(extra='forbid')
    schema_version: str = 'conversion-ai-diagnostic-v1'
    run_id: str
    status: str
    checkpoint: str
    stage: str
    observed_at: str
    active_operation: str | None = None
    targets: list[dict] = Field(default_factory=list)
    analysis_failures: list[dict] = Field(default_factory=list, exclude_if=lambda value: not value)
    limitations: list[str] = Field(default_factory=list)
