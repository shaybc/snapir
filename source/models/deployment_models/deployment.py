from pydantic import Field

from models.common_models.common import SnapirBaseModel, TargetLanguage


class DeploymentDefaults(SnapirBaseModel):
    namespace: str
    replicas: int
    image_pull_policy: str
    container_port: int
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    liveness_path: str
    readiness_path: str
    managed_by_label: str
    schema_version: str = "v1"


class DeploymentTemplateRef(SnapirBaseModel):
    platform: str
    template_dir: str
    defaults_path: str
    environment: str
    schema_version: str = "v1"


class DeploymentSpec(SnapirBaseModel):
    operation_id: str
    service_name: str
    target_language: TargetLanguage
    image_name: str
    port: int
    health_paths: dict = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)
    template_ref: DeploymentTemplateRef
    platform: str
    schema_version: str = "v1"


class RenderedManifest(SnapirBaseModel):
    operation_id: str
    platform: str
    files: dict[str, str] = Field(default_factory=dict)
    validated: bool
    schema_version: str = "v1"


class DeploymentValidationResult(SnapirBaseModel):
    operation_id: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    schema_version: str = "v1"
