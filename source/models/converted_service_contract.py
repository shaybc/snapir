"""The saved callable API of one successfully converted Composer operation."""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, JsonValue, field_validator

from models.service_address import ServiceAddress
from models.service_completion_evidence import ServiceCompletionEvidence


class ConvertedServiceContract(BaseModel):
    """Keep service identity, call structure and completion evidence together."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    application_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    api_revision: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    artifact_reference: str = Field(min_length=1)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    path: str = Field(min_length=1)
    media_types: list[str] = Field(min_length=1)
    request_contract: dict[str, JsonValue] = Field(min_length=1)
    response_contract: dict[str, JsonValue] = Field(min_length=1)
    error_contract: dict[str, JsonValue] = Field(min_length=1)
    api_definition: dict[str, JsonValue] = Field(min_length=1)
    addresses: dict[str, ServiceAddress] = Field(min_length=1)
    completion: ServiceCompletionEvidence
    swagger_url: AnyHttpUrl | None = None
    status: Literal["converted"] = "converted"
    schema_version: Literal["v1"] = "v1"

    @field_validator("path")
    @classmethod
    def require_service_route(cls, value):
        """Keep the route distinct from its environment-specific host."""
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("The service path must start with a single slash")
        return value

    @field_validator("media_types")
    @classmethod
    def require_media_types(cls, values):
        """Reject empty content types in an otherwise non-empty list."""
        if any(not value.strip() for value in values):
            raise ValueError("Media types must not be empty")
        return values

    @field_validator("addresses")
    @classmethod
    def require_environment_names(cls, values):
        """Require an explicit environment identity for each saved address."""
        if any(not name.strip() for name in values):
            raise ValueError("Service address environments must not be empty")
        return values
