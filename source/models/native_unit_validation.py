"""Accepted build and behavioral test evidence for a native candidate bundle."""

from pydantic import BaseModel, Field


class NativeUnitValidation(BaseModel):
    """Build results kept separate from unavailable legacy equivalence proof."""

    build_passed: bool = False
    tests_passed: bool = False
    test_count: int = 0
    executed_test_classes: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    behavioral_equivalence: str = "not_available"
