"""Verified external JDBC artifacts and chart-only fixture-server orchestration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class JdbcDriverArtifact(BaseModel):
    """A complete external driver JAR; the public Java class name is not renamed."""
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    driverClass: str = Field(min_length=1)


class FixtureServerDeployment(BaseModel):
    """Deployment-only settings; none are supplied to application business code."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    status: Literal['prepared', 'unavailable'] = 'unavailable'
    issues: list[str] = Field(default_factory=list)
    bundleId: str = Field(default='', pattern=r'^([a-f0-9]{64})?$')
    manifestHash: str = Field(default='', pattern=r'^([a-f0-9]{64})?$')
    toolRoot: str = ''
    catalogue: str = ''
    catalogueHash: str = Field(default='', pattern=r'^([a-f0-9]{64})?$')
    port: int = Field(default=15432, ge=1024, le=65535)
    repository: str = ''
    digest: str = Field(default='', pattern=r'^(sha256:[a-f0-9]{64})?$')
    fixtureClaim: str = Field(default='', pattern=r'^([a-z0-9][a-z0-9.-]*)?$')
    fixtureMount: str = '/fixtures'
    catalogueInContainer: str = ''
    fixtureRoots: list[str] = Field(default_factory=list)
    assetRootMap: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def complete_enabled_sidecar(self):
        if self.enabled:
            if self.status != 'prepared' or self.issues:
                raise ValueError('Unavailable fixture server cannot be enabled')
            if not all((self.bundleId,self.manifestHash,self.catalogueHash,self.toolRoot,self.catalogue,
                        self.fixtureClaim,self.catalogueInContainer,self.fixtureRoots)):
                raise ValueError('Enabled fixture sidecar requires pinned tools, catalogue and read-only fixture volume')
            for path in [self.fixtureMount,self.catalogueInContainer,*self.fixtureRoots,*self.assetRootMap.values()]:
                if not path.startswith(self.fixtureMount.rstrip('/')+'/') and path != self.fixtureMount:
                    raise ValueError('Container fixture paths must be under the read-only fixture mount')
        return self
