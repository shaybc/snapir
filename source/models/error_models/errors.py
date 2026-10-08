from pydantic import Field

from models.common_models.common import SnapirBaseModel, TargetLanguage
from models.conversion_models.conversion import ValidationFailureClass


class PipelineError(SnapirBaseModel):
    code: str
    message: str
    task_id: str | None = None
    operation_id: str | None = None
    recoverable: bool
    schema_version: str = "v1"


class BlockedOperation(SnapirBaseModel):
    operation_id: str
    blocked_by: list[str] = Field(default_factory=list)
    reason: str
    schema_version: str = "v1"


class HumanReviewItem(SnapirBaseModel):
    item_id: str
    kind: str
    entity_id: str
    summary: str
    evidence_paths: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    blocking_operation_ids: list[str] = Field(default_factory=list)
    schema_version: str = "v1"


class RetryDecision(SnapirBaseModel):
    task_id: str
    attempt_number: int
    max_retries: int
    should_retry: bool
    reason: str
    schema_version: str = "v1"


class UnsupportedTargetLanguageError(PipelineError):
    target_language: TargetLanguage


class ValidationFailureRecord(SnapirBaseModel):
    failure_class: ValidationFailureClass
    operation_id: str
    affected_component_ids: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    recommended_feedback_target: str
    requires_human_review: bool
    schema_version: str = "v1"
