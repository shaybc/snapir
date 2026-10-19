"""Project settings for the generic migration runtime."""

from copy import deepcopy
from typing import Literal

import constants
from models.deployment_models import DeploymentDefaults
from models.external_dependency import ExternalDependencyRule
from models.conversion_requirement import ConversionRequirement

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PipelineConfiguration(BaseModel):
    """Describe project inputs and conversion scope without storing credentials."""

    model_config = ConfigDict(extra="forbid", validate_default=True)
    conversion_strategy: Literal["legacy_components", "behavior_units"] = "legacy_components"
    conversion_requirements: list[ConversionRequirement] = Field(default_factory=list)
    behavior_context_chars: int = Field(default=180000, ge=60000, le=1000000)
    source_root: str = constants.COMPOSER_ROOT
    source_workspace_id: str | None = Field(default=constants.SOURCE_WORKSPACE_ID, min_length=1)
    service_registry_path: str | None = Field(default=None, min_length=1)
    plan_approval_policy: Literal["human", "automatic", "skip"] = "human"
    shared_library_min_usage: int = Field(default=constants.SHARED_LIBRARY_MIN_USAGE, ge=1)
    broad_library_usage_threshold: int = Field(default=constants.BROAD_LIBRARY_USAGE_THRESHOLD, ge=1)
    mapper_jar: str = constants.COMPOSER_MAPPER_JAR
    java_version: Literal[21, 25] = int(constants.JAVA_VERSION)
    java_home: str | None = constants.JAVA_HOME
    output_root: str = constants.OUTPUT_ROOT
    channels: list[str] = Field(default_factory=lambda: deepcopy(constants.TARGET_CHANNELS), min_length=1)
    include_operations: list[str] | None = Field(default_factory=lambda: deepcopy(constants.INCLUDE_OPERATIONS))
    exclude_operations: list[str] | None = Field(default_factory=lambda: deepcopy(constants.EXCLUDE_OPERATIONS))
    target_languages: list[Literal["java"]] = Field(default_factory=lambda: deepcopy(constants.TARGET_LANGUAGES), min_length=1)
    model_name: str = constants.AGENT_MODEL
    model_base_url: str = constants.LITELLM_BASE_URL
    auto_rerun_impacted_operations: bool = constants.AUTO_RERUN_IMPACTED_OPERATIONS
    model_provider: Literal["gemini", "litellm", "mock"] = constants.MODEL_PROVIDER
    classpath_jars: list[str] = Field(default_factory=lambda: deepcopy(constants.CLASSPATH_JARS))
    external_dependencies: list[ExternalDependencyRule] = Field(default_factory=list)
    composer_behavior_document: str = Field(default="docs/comp-manual/wsbcc_developer_manual_v2.md", exclude=True)
    maven_settings_path: str | None = constants.MAVEN_SETTINGS_PATH
    approved_maven_repository_urls: list[str] = Field(default_factory=lambda: deepcopy(constants.APPROVED_MAVEN_REPOSITORY_URLS))
    maven_local_repository: str | None = constants.MAVEN_LOCAL_REPOSITORY
    allowed_ibm_artifacts: list[str] = Field(default_factory=lambda: deepcopy(constants.ALLOWED_IBM_ARTIFACTS))
    allowed_ibm_classes: list[str] = Field(default_factory=lambda: deepcopy(constants.ALLOWED_IBM_CLASSES))
    deployment_template_dir: str | None = constants.DEPLOYMENT_TEMPLATE_DIR
    deployment_values: dict[str, dict] = Field(default_factory=lambda: deepcopy(constants.DEPLOYMENT_VALUES))
    deployment_defaults: DeploymentDefaults = Field(default_factory=lambda: DeploymentDefaults(**deepcopy(constants.DEPLOYMENT_DEFAULTS)))
    deployment_platform: str = constants.DEPLOYMENT_PLATFORM
    deployment_environment: str = constants.DEPLOYMENT_ENVIRONMENT
    deployment_env_vars: dict[str, str] = Field(default_factory=lambda: deepcopy(constants.DEPLOYMENT_ENV_VARS))
    runtime_validation_mode: Literal["disabled", "dummy"] = constants.RUNTIME_VALIDATION_MODE
    eclipse_classpath_variables: dict[str, str] = Field(default_factory=lambda: deepcopy(constants.ECLIPSE_CLASSPATH_VARIABLES))
    model_api_key_environment: str = constants.MODEL_API_KEY_ENVIRONMENT
    model_timeout_seconds: int = Field(default=constants.MODEL_TIMEOUT_SECONDS, gt=0)
    max_model_attempts: int = Field(default=constants.MAX_MODEL_ATTEMPTS, ge=1, le=10)
    max_operations_per_batch: int = Field(default=constants.MAX_OPERATIONS_PER_BATCH, ge=1)
    gate_policies: dict[str, Literal["human", "automatic", "skip"]] = Field(
        default_factory=lambda: deepcopy(constants.GATE_POLICIES)
    )

    max_agent_task_retries: int = Field(default=constants.MAX_AGENT_TASK_RETRIES, ge=1)
    max_parallel_conversion_workers: int = Field(default=constants.MAX_PARALLEL_CONVERSION_WORKERS, ge=1)
    max_parallel_llm_tasks: int = Field(default=constants.MAX_PARALLEL_LLM_TASKS, ge=1)
    max_parallel_build_tasks: int = Field(default=constants.MAX_PARALLEL_BUILD_TASKS, ge=1)
    inter_batch_delay_secs: float = Field(default=constants.INTER_BATCH_DELAY_SECS, ge=0)
    enable_git: bool = constants.ENABLE_GIT

    @field_validator("gate_policies")
    @classmethod
    def validate_gate_numbers(cls, value):
        """Reject misspelled gate numbers rather than silently defaulting their policy."""
        if set(value) - {"1", "2", "3", "4"}:
            raise ValueError("Gate numbers must be 1 through 4")
        return {**deepcopy(constants.GATE_POLICIES), **value}

    @model_validator(mode="after")
    def apply_explicit_retention(self):
        """Carry explicit library retention into existing exact client dependency checks."""
        for rule in self.external_dependencies:
            if rule.treatment == "retain":
                if rule.class_name and rule.class_name not in self.allowed_ibm_classes:
                    self.allowed_ibm_classes.append(rule.class_name)
                if rule.maven_coordinates and rule.maven_coordinates not in self.allowed_ibm_artifacts:
                    self.allowed_ibm_artifacts.append(rule.maven_coordinates)
        return self

    @model_validator(mode="after")
    def validate_library_thresholds(self):
        """Require a non-empty small-sharing range between configured thresholds."""
        if self.broad_library_usage_threshold < self.shared_library_min_usage:
            raise ValueError("broad_library_usage_threshold must be at least shared_library_min_usage")
        return self
