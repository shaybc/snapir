"""Represent static source references and their inherited operation consumers."""

from pydantic import BaseModel, Field


class JavaSourceDependency(BaseModel):
    """One resolved source-reference site, not a runtime invocation count."""

    dependency_id: str
    caller_implementation_id: str
    target_implementation_id: str
    source_offset: int
    reference_kind: str
    reference_name: str


class JavaDependencyUse(BaseModel):
    """Link an original XML use to a reachable Java source-reference site."""

    use_id: str
    source_use_id: str
    dependency_id: str
    operation_key: str
    operation_id: str
    channel: str | None = None
    implementation_id: str
    reference_count: int = Field(default=1, ge=1)


class JavaDependencyIssue(BaseModel):
    """Keep source-resolution problems scoped to the owning original class."""

    implementation_id: str
    message: str


class JavaSourceDependencyGraph(BaseModel):
    """Capture syntax-derived dependencies without claiming full compiler attribution."""

    dependencies: list[JavaSourceDependency] = Field(default_factory=list)
    uses: list[JavaDependencyUse] = Field(default_factory=list)
    issues: list[JavaDependencyIssue] = Field(default_factory=list)
    analysis_scope: str = "Static source-type references; reflection, overload resolution and runtime dispatch are not proven"
