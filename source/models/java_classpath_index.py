"""Available compiled classes and classpath discovery diagnostics."""

from pydantic import BaseModel, Field


class JavaClasspathIndex(BaseModel):
    """Map fully qualified binary types to JAR or JDK locations."""

    classes: dict[str, list[str]] = Field(default_factory=dict)
    libraries: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
