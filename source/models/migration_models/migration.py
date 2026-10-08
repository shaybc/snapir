from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator

from models.common_models.common import (
    SnapirBaseModel,
    TargetLanguage,
    TaskStatus,
    _require_timezone,
)


class OperationGrouping(str, Enum):
    one_step = "one_step"
    multi_step_linear = "multi_step_linear"
    branch_heavy = "branch_heavy"
    db_bound = "db_bound"
    shared_format_context = "shared_format_context"
    unusual_manual_review = "unusual_manual_review"


class ServiceCandidate(SnapirBaseModel):
    operation_id: str
    channel: str
    group: OperationGrouping
    target_language: TargetLanguage
    estimated_complexity: int
    schema_version: str = "v1"


class MigrationTaskPacket(SnapirBaseModel):
    task_id: str
    run_id: str
    operation_id: str
    channel: str
    target_language: TargetLanguage
    group: OperationGrouping
    generation_notes: list[str] = Field(default_factory=list)
    status: TaskStatus
    schema_version: str = "v1"


class MigrationBatch(SnapirBaseModel):
    batch_id: str
    run_id: str
    task_packets: list[MigrationTaskPacket] = Field(default_factory=list)
    is_pilot: bool
    status: TaskStatus
    schema_version: str = "v1"


class MigrationPlan(SnapirBaseModel):
    plan_id: str
    run_id: str
    batches: list[MigrationBatch] = Field(default_factory=list)
    total_operations: int
    unusual_count: int
    status: TaskStatus
    schema_version: str = "v1"


class ManualOperationReviewRecord(SnapirBaseModel):
    operation_id: str
    review_status: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    reason_for_manual_review: list[str] = Field(default_factory=list)
    generation_notes: list[str] = Field(default_factory=list)
    schema_version: str = "v1"

    @field_validator("reviewed_at")
    @classmethod
    def timestamps_have_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_timezone(value)
