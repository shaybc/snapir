"""Ordered Eclipse build-path evidence for one project."""
from pydantic import BaseModel, Field


class ProjectClasspathEntry(BaseModel):
    """One expanded entry with its raw declaration and expansion precedence."""
    kind: str
    path: str
    reference: str = ''
    exported: bool = False
    order_known: bool = True
    rank: list[int] = Field(default_factory=list)
    chain: list[str] = Field(default_factory=list)


class ProjectClasspath(BaseModel):
    """Keep declarations separate from the effective, exported dependency expansion."""
    directory: str
    declared: list[ProjectClasspathEntry] = Field(default_factory=list)
    entries: list[ProjectClasspathEntry] = Field(default_factory=list)
