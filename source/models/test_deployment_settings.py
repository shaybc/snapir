"""Connection settings for testing manually deployed OpenShift services."""

from copy import deepcopy

import constants
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator


def _setting(name, title, **constraints):
    """Read independent defaults from the central settings when a profile is created."""
    return Field(default_factory=lambda: deepcopy(constants.TEST_DEPLOYMENT_DEFAULTS[name]),
                 title=title, **constraints)


class TestDeploymentSettings(BaseModel):
    """Describe the external address of a manually deployed test service."""

    model_config = ConfigDict(extra="forbid", validate_default=True)
    service_base_url: str = _setting("service_base_url", "Test service base URL")
    service_external_port: int | None = _setting("service_external_port", "External service port (auto or number)", ge=1, le=65535)
    service_route_pattern: str = _setting("service_route_pattern", "Service hostname or route-path pattern")

    @field_validator("service_base_url")
    @classmethod
    def validate_optional_http_url(cls, value):
        """Allow unfinished settings, but require HTTP(S) addresses when provided."""
        if value:
            TypeAdapter(HttpUrl).validate_python(value)
        return value
