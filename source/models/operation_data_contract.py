"""Explicit typed interfaces connecting native format and step bundles."""

from pydantic import BaseModel, ConfigDict, Field
from models.operation_dependency import OperationDependency
from models.operation_resource import OperationResource


class NativeApiContract(BaseModel):
    """A planned native type and exact public methods it must expose."""

    model_config = ConfigDict(extra="forbid")
    type_name: str
    method_signatures: list[str] = Field(default_factory=list)


class UnitContract(BaseModel):
    """Required APIs, dependencies and evidence-backed requirements for a unit."""

    model_config = ConfigDict(extra="forbid")
    unit_id: str
    apis: list[NativeApiContract] = Field(min_length=1)
    dependency_units: list[str] = Field(default_factory=list)
    requirements: dict[str, str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class OperationDataContract(BaseModel):
    """Reconciled explicit Java data types and all configured-unit interfaces."""

    model_config = ConfigDict(extra="forbid")
    sources: list[dict] = Field(min_length=1)
    units: list[UnitContract] = Field(min_length=1)
    service_api: NativeApiContract
    request_type: str
    success_type: str
    error_type: str
    request_wire_type: str | None = None
    success_wire_type: str | None = None
    error_wire_type: str | None = None
    service_requirements: dict[str, str] = Field(default_factory=dict)
    step_dependencies: list[OperationDependency] = Field(default_factory=list)
    runtime_resources: list[OperationResource] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    schema_version: str = "v1"
