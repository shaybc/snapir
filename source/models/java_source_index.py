"""Describe discovered workspace source roots and Java class locations."""

from pydantic import BaseModel, Field


class JavaSourceIndex(BaseModel):
    """Record source ownership, project references, and discovery diagnostics."""

    workspace_root: str
    source_roots: dict[str, list[str]] = Field(default_factory=dict)
    project_references: dict[str, list[str]] = Field(default_factory=dict)
    classes: dict[str, list[str]] = Field(default_factory=dict)
    class_projects: dict[str, str] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
