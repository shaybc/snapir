"""Candidate implementations for one indivisible component group, never accepted units."""
from pydantic import BaseModel, ConfigDict, Field
from models.native_component_contract import NativeComponentContract
from models.native_unit_bundle import NativeSourceFile
from models.maven_dependency import MavenDependency
from models.checklist_code_location import ChecklistCodeLocation


class NativeComponentBundle(BaseModel):
    """Keep component interfaces, Java and executed-test obligations in one response."""
    model_config = ConfigDict(extra='forbid')
    contracts: dict[str, NativeComponentContract] = Field(min_length=1)
    files: list[NativeSourceFile] = Field(min_length=1)
    dependencies: list[MavenDependency] = Field(default_factory=list)
    coverage: dict[str, list[str]] = Field(default_factory=dict)
    checklist_implementations: dict[str, list[ChecklistCodeLocation]] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

