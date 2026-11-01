"""Bounded, advisory test-strength measurement for technically accepted units."""
from pydantic import BaseModel, ConfigDict, Field


class UnitMutationSettings(BaseModel):
    """PIT runs by default; its score and availability never decide acceptance."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = True
    timeout_seconds: int = Field(default=180, ge=1, le=3600)
    recommended_score: int = Field(default=80, ge=0, le=100)

