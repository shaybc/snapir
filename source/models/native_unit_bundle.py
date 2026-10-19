"""Multi-file native code and tests returned for one agreed behavior contract."""

from pydantic import BaseModel, ConfigDict, Field
from models.maven_dependency import MavenDependency
from models.operation_data_contract import UnitContract, OperationDataContract


class NativeSourceFile(BaseModel):
    """One text Java source under a safe Maven source directory."""

    model_config = ConfigDict(extra="forbid")
    path: str
    content: str


class NativeUnitBundle(BaseModel):
    """Candidate native implementation with test and requirement evidence."""

    model_config = ConfigDict(extra="forbid")
    files: list[NativeSourceFile] = Field(min_length=1)
    dependencies: list[MavenDependency] = Field(default_factory=list)
    coverage: dict[str, list[str]] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    unit_contract: UnitContract | None = None
    input_type: str | None = None
    output_type: str | None = None
    wire_type: str | None = None
    operation_contract: OperationDataContract | None = None
    schema_version: str = "v1"
