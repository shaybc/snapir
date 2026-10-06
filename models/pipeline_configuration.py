"""Project settings for the generic migration runtime."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PipelineConfiguration(BaseModel):
    """Describe project inputs and conversion scope without storing credentials."""

    model_config = ConfigDict(extra="forbid")
    source_root: str
    mapper_jar: str
    output_root: str
    channels: list[str] = Field(min_length=1)
    include_operations: list[str] | None = None
    exclude_operations: list[str] | None = None
    target_languages: list[Literal["java"]] = Field(default_factory=lambda: ["java"], min_length=1)
    model_name: str = "gemini/gemini-2.5-pro"
    model_base_url: str = ""
    auto_rerun_impacted_operations: bool = True
    model_provider: Literal["gemini", "litellm", "mock"] = "gemini"
    classpath_jars: list[str] = Field(default_factory=list)
    maven_settings_path: str | None = None
    approved_maven_repository_urls: list[str] = Field(default_factory=list)
    maven_local_repository: str | None = None
    allowed_ibm_artifacts: list[str] = Field(default_factory=list)
    allowed_ibm_classes: list[str] = Field(default_factory=list)
    deployment_template_dir: str | None = None
    deployment_values: dict[str, dict] = Field(default_factory=dict)
    eclipse_classpath_variables: dict[str, str] = Field(default_factory=dict)
    model_api_key_environment: str = "GOOGLE_API_KEY"
    model_timeout_seconds: int = Field(default=180, gt=0)
    max_model_attempts: int = Field(default=3, ge=1, le=10)
    max_operations_per_batch: int = Field(default=5, ge=1)
    gate_policies: dict[str, Literal["human", "automatic", "skip"]] = Field(
        default_factory=lambda: {str(number): "human" for number in range(1, 5)}
    )

    @field_validator("gate_policies")
    @classmethod
    def validate_gate_numbers(cls, value):
        """Reject misspelled gate numbers rather than silently defaulting their policy."""
        if set(value) - {"1", "2", "3", "4"}:
            raise ValueError("Gate numbers must be 1 through 4")
        return value
