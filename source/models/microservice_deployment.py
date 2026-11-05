"""Editable, secret-free deployment input independent of optional standalone files."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator, field_validator
from models.database_pool_settings import DatabasePoolSettings
from models.jdbc_image_variant import JdbcDriverArtifact, FixtureServerDeployment


class OperationDeployment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    identity: str = Field(min_length=1)
    database: str | None = 'default'
    initialization: dict[str, JsonValue] = Field(default_factory=dict)


class HttpDeployment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(pattern=r'^/[^\s{}?#]*$')
    port: int = Field(default=8080, ge=1024, le=65535)


class ImageDeployment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repository: str = ''
    digest: str = Field(default='', pattern=r'^(sha256:[a-f0-9]{64})?$')
    baseImage: str = Field(default='eclipse-temurin:25-jre',pattern=r'^[A-Za-z0-9_./:@-]+$')
    jdbcDriver: JdbcDriverArtifact | None = None


class DeploymentSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    namespace: str = ''
    replicas: int = Field(default=1, ge=1)
    image: ImageDeployment = Field(default_factory=ImageDeployment)
    cpuRequest: str = '250m'
    cpuLimit: str = '1'
    memoryRequest: str = '256Mi'
    memoryLimit: str = '1Gi'


class MicroserviceDeployment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schemaVersion: Literal['native-microservice-v1'] = 'native-microservice-v1'
    operation: OperationDeployment
    http: HttpDeployment
    databases: dict[str, DatabasePoolSettings] = Field(default_factory=dict)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    transactionPolicy: Literal['preserve-source'] = 'preserve-source'
    demoInfrastructure: FixtureServerDeployment | None = None

    @field_validator('databases')
    @classmethod
    def check_names(cls, databases):
        import re
        if any(not re.fullmatch('[A-Za-z0-9_-]+',name) for name in databases):
            raise ValueError('Database names must be simple, exact logical identifiers')
        return databases

    @model_validator(mode='after')
    def check_database(self):
        if self.operation.database is not None and self.operation.database not in self.databases:
            raise ValueError('Operation selects an unknown database: ' + self.operation.database)
        return self
