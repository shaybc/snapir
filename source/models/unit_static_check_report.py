"""Mapping/exclusion decisions and supporting signals, never behavioral acceptance."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class UnitStaticCheckReport(BaseModel):
    """Warnings require targeted comparison; neither literal presence nor a valid map proves equivalence."""
    model_config = ConfigDict(extra='forbid')
    unit_id: str
    source_manifest_hash: str
    configuration_hash: str
    candidate_hash: str = ''
    policy_hash: str = ''
    tool_hash: str | None = None
    status: Literal['mapping_valid', 'mapping_invalid', 'verification_incomplete', 'facts_disabled_for_test'] = 'verification_incomplete'
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    literal_checks: list[dict[str, Any]] = Field(default_factory=list)
    xml_checks: list[dict[str, Any]] = Field(default_factory=list)
    comparison_requests: list[dict[str, Any]] = Field(default_factory=list)
    comparison_cases: dict[str, dict[str, Any]] = Field(default_factory=dict)
    configuration_controls: list[dict[str, Any]] = Field(default_factory=list)
    authorization_receipts: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_gate_enabled: Literal[False] = False
    behavioral_verification: Literal['not_decided'] = 'not_decided'
    schema_version: Literal['unit-static-checks-v1'] = 'unit-static-checks-v1'
