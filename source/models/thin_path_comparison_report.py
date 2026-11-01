"""Experiment-only paired observations with explicit comparison limitations."""
from pydantic import Field
from models.boundary_comparison_report import BoundaryComparisonReport


class ThinPathComparisonReport(BoundaryComparisonReport):
    """Keep unobservable presence/partial writes separate from actual behavior differences."""
    limitations: list[dict] = Field(default_factory=list)
    auto_binding: list[dict] = Field(default_factory=list)
