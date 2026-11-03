"""Describe a configured unit's comparison contract before verification is implemented."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from models.legacy_boundary_method import LegacyBoundaryMethod
from models.unit_reachable_slice import UnitReachableSlice
from models.configured_setup_binding import ConfiguredSetupBinding
from models.unit_parser_checklist import UnitParserChecklist


class UnitVerificationBoundary(BaseModel):
    """Record analysis evidence without claiming that native behavior was verified."""

    model_config = ConfigDict(extra='forbid')

    unit_id: str
    unit_fingerprint: str
    operation_identity: str
    kind: Literal['request_unformat', 'response_format', 'configured_step']
    implementation_class: str | None = None
    method_name: Literal['unformat', 'format', 'execute']
    parameter_contract: list[str]
    return_contract: str
    inputs: list[str]
    observable_results: list[str]
    setup_class_roots: list[str] = Field(default_factory=list)
    setup_bindings: list[ConfiguredSetupBinding] = Field(default_factory=list)
    configuration_hash: str
    source_manifest_hash: str
    legacy_method: LegacyBoundaryMethod | None = None
    reachable_slice: UnitReachableSlice | None = None
    parser_checklist: UnitParserChecklist | None = None
    basic_parser_checklist: UnitParserChecklist | None = None
    configuration_preparation: dict = Field(default_factory=dict)
    analysis_status: Literal['identified', 'verification_incomplete'] = 'verification_incomplete'
    verification_status: Literal['not_run'] = 'not_run'
    issues: list[str] = Field(default_factory=list)
    schema_version: str = 'unit-boundary-v1'
