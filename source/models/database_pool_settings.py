"""Named JDBC pools contain deployment settings and credential references only."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CredentialSecret(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, pattern=r'^[a-z0-9][a-z0-9.-]*$')
    usernameKey: str = Field(default='username',min_length=1,pattern=r'^[A-Za-z0-9._-]+$')
    passwordKey: str = Field(default='password',min_length=1,pattern=r'^[A-Za-z0-9._-]+$')


class PoolSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    minimumIdle: int = Field(default=0, ge=0)
    maximumPoolSize: int = Field(default=10, ge=1)
    connectionTimeoutMs: int = Field(default=30000, ge=250)
    maxLifetimeMs: int = Field(default=1800000, ge=30000)

    @model_validator(mode='after')
    def check_capacity(self):
        if self.minimumIdle > self.maximumPoolSize:
            raise ValueError('minimumIdle exceeds maximumPoolSize')
        return self


class DatabasePoolSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    jdbcUrl: str = ''
    driverClass: str = ''
    credentialsSecret: CredentialSecret
    pool: PoolSettings = Field(default_factory=PoolSettings)
