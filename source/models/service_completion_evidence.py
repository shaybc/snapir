"""Required completion evidence for publishing a converted operation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ServiceCompletionEvidence(BaseModel):
    """Identify the successful run and its completed conversion checks."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_run_id: str = Field(min_length=1)
    validation_report_reference: str = Field(min_length=1)
    conversion_passed: Literal[True]
    package_passed: Literal[True]
    tests_passed: Literal[True]
    review_approved: Literal[True]
    gates_approved: Literal[True]
