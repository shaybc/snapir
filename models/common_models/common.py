from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must include timezone information")
    return value


class SnapirBaseModel(BaseModel):
    model_config = {"use_enum_values": False}


class RunMode(str, Enum):
    single_channel = "single_channel"
    multi_channel = "multi_channel"
    full_inventory = "full_inventory"


class TargetLanguage(str, Enum):
    java = "java"
    nodejs = "nodejs"
    python = "python"


class RunConfig(SnapirBaseModel):
    run_id: str
    run_mode: RunMode
    source_root: str
    vault_root: str
    output_root: str
    db_path: str
    env_file: str | None = None
    target_channels: list[str] = Field(default_factory=list)
    composer_mapper_channel_filter: str | None = None
    target_languages: list[TargetLanguage] = Field(default_factory=list)
    enable_git: bool
    artifact_schema_version: str
    max_agent_task_retries: int
    max_parallel_conversion_workers: int
    max_parallel_llm_tasks: int
    max_parallel_build_tasks: int
    max_operations_per_batch: int
    model_name: str
    model_base_url: str
    auto_rerun_impacted_operations: bool
    include_operations: list[str] | None = None
    exclude_operations: list[str] | None = None
    schema_version: str = "v1"


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    validated = "validated"
    failed = "failed"
    needs_rerun = "needs_rerun"
    blocked = "blocked"
    needs_human_review = "needs_human_review"
    started = "started"
    orphaned_temp = "orphaned_temp"
    cancelled = "cancelled"


class ProcessLock(SnapirBaseModel):
    task_id: str
    run_id: str
    process_id: int
    hostname: str
    started_at: datetime
    heartbeat_at: datetime
    schema_version: str = "v1"

    @field_validator("started_at", "heartbeat_at")
    @classmethod
    def timestamps_have_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class InvalidationEvent(SnapirBaseModel):
    event_id: str
    run_id: str
    corrected_artifact_id: str
    corrected_artifact_kind: str
    change_reason: str
    old_hash: str
    new_hash: str
    affected_operation_ids: list[str] = Field(default_factory=list)
    affected_artifact_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    schema_version: str = "v1"

    @field_validator("created_at")
    @classmethod
    def timestamps_have_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value)
