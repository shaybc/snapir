"""Observed equivalence evidence with explicit coverage gaps; not an acceptance record."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class BoundaryComparisonReport(BaseModel):
    """Retain observed results and coverage gaps, never an Accepted-unit decision."""
    model_config = ConfigDict(extra='forbid')
    unit_id: str
    status: Literal['matched_observed_cases', 'differences_found', 'verification_incomplete'] = 'verification_incomplete'
    source_manifest_hash: str
    configuration_hash: str
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    execution_environment: dict[str, Any] = Field(default_factory=dict)
    logging_comparison_policy: dict[str, Any] = Field(default_factory=dict)
    cases: list[dict[str, Any]] = Field(default_factory=list)
    unexecuted_case_ids: list[str] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    acceptance_gate_enabled: Literal[False] = False
    exhaustive_equivalence: Literal[False] = False
    schema_version: Literal['boundary-comparison-v1'] = 'boundary-comparison-v1'

