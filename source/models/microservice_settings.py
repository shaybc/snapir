"""Approval-gated packaging of accepted native operations as Spring Boot Helm services."""
from pydantic import BaseModel, ConfigDict


class MicroserviceSettings(BaseModel):
    """Keep wrapper packaging separate from image publication and cluster deployment."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = True
    helm_executable: str = 'helm'
    require_helm_validation: bool = True
    kubernetes_version: str = '1.34.0'
