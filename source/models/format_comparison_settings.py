"""Opt-in diagnostic execution limits, independent of conversion acceptance policy."""
from pydantic import BaseModel, ConfigDict, Field


class FormatComparisonSettings(BaseModel):
    """Execution is disabled unless explicitly enabled; results never grant acceptance."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    max_cases: int = Field(default=64, ge=1, le=512)
    case_timeout_seconds: float = Field(default=15, gt=0, le=120)
    discovery_request_chars: int = Field(default=900000, ge=1000, le=900000)
    compare_exception_messages: bool = False
    collect_facts: bool = True

