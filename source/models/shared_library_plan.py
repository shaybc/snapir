"""Describe reviewed ownership of original components and their consuming services."""

from pydantic import BaseModel, Field


class SharedLibrary(BaseModel):
    """Group reusable components into one run-owned Maven library."""

    library_id: str
    version: str
    component_keys: list[str] = Field(default_factory=list)
    consumers: list[str] = Field(default_factory=list)


class SharedLibraryPlan(BaseModel):
    """Assign each inventoried component to a library or an operation-local project."""

    fingerprint: str
    libraries: list[SharedLibrary] = Field(default_factory=list)
    assignments: dict[str, str | None] = Field(default_factory=dict)
    consumers: dict[str, list[str]] = Field(default_factory=dict)
    usage_counts: dict[str, int] = Field(default_factory=dict, description="Distinct channel-and-operation consumers per component; used for sharing thresholds.")
    reference_counts: dict[str, int] = Field(default_factory=dict, description="Raw configured and Java dependency references, retained for diagnostics.")
    shared_library_min_usage: int = 5
    broad_library_usage_threshold: int = 10
    diagnostics: list[str] = Field(default_factory=list)
    conversion_order: list[str] = Field(default_factory=list)
    library_dependencies: dict[str, list[str]] = Field(default_factory=dict)
    library_build_order: list[str] = Field(default_factory=list)
    dependency_analysis: str = "Static source references; dynamic/reflection and compiler-level symbol attribution remain outside this inventory"
