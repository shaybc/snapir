"""Separate dependency-coordinate proposal; artifacts still require real verification."""
from pydantic import BaseModel, ConfigDict, Field
from models.maven_dependency import MavenDependency


class NativeDependencyProposal(BaseModel):
    """Propose pinned artifacts for unresolved imports only; compilation verifies availability."""
    model_config = ConfigDict(extra='forbid')
    dependencies: list[MavenDependency] = Field(min_length=1)
