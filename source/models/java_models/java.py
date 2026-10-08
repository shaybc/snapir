from pydantic import Field

from models.common_models.common import SnapirBaseModel, TargetLanguage


class JavaPackageSpec(SnapirBaseModel):
    group_id: str
    artifact_id: str
    version: str
    dependencies: list[dict] = Field(default_factory=list)
    schema_version: str = "v1"


class JavaServiceSpec(SnapirBaseModel):
    operation_id: str
    service_name: str
    package_spec: JavaPackageSpec
    main_class: str
    port: int
    health_path: str
    schema_version: str = "v1"


class JavaProjectSpec(SnapirBaseModel):
    service_spec: JavaServiceSpec
    src_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    schema_version: str = "v1"


class JavaBuildSpec(SnapirBaseModel):
    maven_goals: list[str] = Field(default_factory=list)
    java_version: str
    spring_boot_version: str
    schema_version: str = "v1"


class JavaBuildResult(SnapirBaseModel):
    operation_id: str
    target_language: TargetLanguage
    success: bool
    stdout: str
    stderr: str
    duration_ms: int
    schema_version: str = "v1"
