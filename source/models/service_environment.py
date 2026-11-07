"""Non-secret address conventions for one OpenShift environment."""
from pydantic import BaseModel, ConfigDict, Field


class ServiceEnvironment(BaseModel):
    """Select internal DNS and an explicit externally accessible URL pattern."""
    model_config = ConfigDict(extra='forbid')
    namespace: str = Field(default='', pattern=r'^[a-z0-9-]*$')
    cluster_domain: str = Field(default='cluster.local', pattern=r'^[a-z0-9.-]+$')
    external_url_pattern: str = ''
    service_port: int = Field(default=8080, ge=1, le=65535)
