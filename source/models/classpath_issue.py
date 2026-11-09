"""A classpath diagnostic tied to the project and reference that produced it."""

from pydantic import BaseModel


class ClasspathIssue(BaseModel):
    """Keep readable messages while preserving provenance for dependency-scoped validation."""

    project: str | None = None
    reference: str
    kind: str
    detail: str
