"""Available compiled classes and classpath discovery diagnostics."""

from pydantic import BaseModel, Field, PrivateAttr
from models.classpath_issue import ClasspathIssue
from models.project_classpath import ProjectClasspath


class JavaClasspathIndex(BaseModel):
    """Map fully qualified binary types to JAR or JDK locations."""

    classes: dict[str, list[str]] = Field(default_factory=dict)
    libraries: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    issue_details: list[ClasspathIssue] = Field(default_factory=list)
    metadata_fingerprints: dict[str, str | None] = Field(default_factory=dict)
    project_references: dict[str, list[str]] = Field(default_factory=dict)
    container_resolutions: list[dict] = Field(default_factory=list)
    project_classpaths: dict[str, ProjectClasspath] = Field(default_factory=dict)
    binary_resolutions: list[dict] = Field(default_factory=list)
    active_project: str | None = None
    _project_views: dict = PrivateAttr(default_factory=dict)
    _archive_hashes: dict = PrivateAttr(default_factory=dict)
