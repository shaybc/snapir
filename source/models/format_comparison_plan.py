"""Immutable-input diagnostic plan for a basic format or a complete configured tree."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models.native_unit_bundle import NativeSourceFile
from models.native_verification_binding import NativeVerificationBinding
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.format_comparison_case import FormatComparisonCase
from models.format_context_requirement import FormatContextDiscovery


class FormatComparisonEntry(BaseModel):
    """Select one exact production overload for one direction."""
    model_config = ConfigDict(extra='forbid')
    direction: Literal['format', 'unformat', 'step_execute']
    binding: NativeVerificationBinding


class FormatComparisonPlan(BaseModel):
    """Declare data and API wiring only, never executable adapter code."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['format-comparison-v1'] = 'format-comparison-v1'
    label: str
    scope: Literal['basic', 'configured']
    original_unit: dict
    native_sources: list[NativeSourceFile] = Field(min_length=1)
    entries: dict[str, FormatComparisonEntry] = Field(min_length=1)
    cases: list[FormatComparisonCase] = Field(min_length=1)
    discovery: FormatContextDiscovery = Field(default_factory=FormatContextDiscovery)
    original_framework: BoundaryHarnessBinding = Field(default_factory=lambda: BoundaryHarnessBinding(
        adapter_class='il.co.dcd.verification.harness.LegacyBoundaryAdapter'))
    native_classpath: list[str] = Field(default_factory=list)
    native_external_bindings: dict[str, str] = Field(default_factory=dict)
    explicit_scenarios: bool = Field(default=False,exclude_if=lambda value:not value)
    fixture_manifest_hash: str | None = Field(default=None,exclude_if=lambda value:value is None)
    original_step_implementation: str | None = Field(default=None,exclude_if=lambda value:value is None)
    original_packages: dict[str,str] = Field(default_factory=dict,exclude_if=lambda value:not value)
    original_packages: dict[str,str] = Field(default_factory=dict,exclude_if=lambda value:not value)

    @model_validator(mode='after')
    def distinct_cases(self):
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError('Comparison cases require unique identities')
        for case in self.cases:
            if case.binding_id not in self.entries:
                raise ValueError('Case selects an unknown directional binding')
            if case.roundtrip_binding_id is not None and (case.roundtrip_binding_id not in self.entries or
                    self.entries[case.binding_id].direction != 'format' or self.entries[case.roundtrip_binding_id].direction != 'unformat'):
                raise ValueError('Round trips require an explicit format entry followed by an unformat entry')
        if self.original_framework.adapter_class != 'il.co.dcd.verification.harness.LegacyBoundaryAdapter' or self.original_framework.sources:
            raise ValueError('Use the trusted Composer adapter, not supplied adapter source')
        return self

