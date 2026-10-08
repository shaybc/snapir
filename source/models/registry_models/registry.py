from pydantic import Field

from models.common_models.common import SnapirBaseModel, TargetLanguage, TaskStatus
from models.conversion_models.conversion import BlockingReason, ConversionStatus


class SourceArtifactRecord(SnapirBaseModel):
    artifact_id: str
    kind: str
    logical_id: str
    source_path: str
    source_hash: str
    shared: bool
    used_by_count: int
    used_by_ids: list[str] = Field(default_factory=list)
    conversion_status: str
    schema_version: str = "v1"


class GeneratedArtifactRecord(SnapirBaseModel):
    artifact_id: str
    kind: str
    logical_id: str
    source_path: str
    source_hash: str
    target_language: TargetLanguage
    artifact_schema_version: str
    generated_path: str
    status: TaskStatus
    blocking_reason: BlockingReason | None = None
    invalidation_event_id: str | None = None
    attempt_number: int
    schema_version: str = "v1"


class ComponentRegistryRecord(SnapirBaseModel):
    component_id: str
    artifact_kind: str
    logical_id: str
    source_path: str
    source_hash: str
    target_language: TargetLanguage
    artifact_schema_version: str
    generated_path: str
    status: ConversionStatus
    used_by_operations: list[str] = Field(default_factory=list)
    used_by_validated_operations: int
    schema_version: str = "v1"


class ArtifactReuseDecision(SnapirBaseModel):
    should_reuse: bool
    component_id: str | None = None
    generated_path: str | None = None
    reason: str
