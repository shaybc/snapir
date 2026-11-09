"""Bind an ordinary retained binary to original bytes and a reproducible Maven identity."""

from pydantic import BaseModel, ConfigDict, Field
from models.maven_dependency import MavenDependency


class RetainedLibrary(BaseModel):
    """Candidate availability is evidence, never an instruction to package every library."""

    model_config = ConfigDict(extra='forbid')
    path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    dependency: MavenDependency
    original_coordinates: str | None = None
    pom_sha256: str | None = None
    ibm: bool = False
