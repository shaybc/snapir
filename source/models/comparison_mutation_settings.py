"""Explicit advisory differential-mutation budgets, independent of PIT and AI retries."""
from pydantic import BaseModel,ConfigDict,Field


class ComparisonMutationSettings(BaseModel):
    """Limit disposable mutations; surviving code never changes production acceptance."""
    model_config=ConfigDict(extra='forbid')
    enabled: bool=False
    max_mutants: int=Field(default=4,ge=1,le=32)
    timeout_seconds: float=Field(default=600,gt=0,le=900)

