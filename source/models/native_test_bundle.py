"""Tests-only response for a frozen native production implementation."""
from pydantic import BaseModel, ConfigDict, Field
from models.native_unit_bundle import NativeSourceFile


class NativeTestBundle(BaseModel):
    """Executable test files and requirement links; no production edits or API metadata."""
    model_config = ConfigDict(extra='forbid')
    files: list[NativeSourceFile] = Field(min_length=1)
    coverage: dict[str,list[str]] = Field(default_factory=dict)
    unresolved_questions: list[str] = Field(default_factory=list)
    fixture_manifest_hash: str | None = Field(default=None,exclude_if=lambda value:value is None)
    scenario_methods: dict[str,str] = Field(default_factory=dict,exclude_if=lambda value:not value)
