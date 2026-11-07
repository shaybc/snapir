"""Environment-specific connection configuration for a converted service."""

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class ServiceAddress(BaseModel):
    """Supply a known base URL or the deployment property that provides it."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    base_url: AnyHttpUrl | None = None
    base_url_property: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    internal_base_url: AnyHttpUrl | None = None
    external_base_url: AnyHttpUrl | None = None
    service_name: str | None = Field(default=None, pattern=r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$')
    namespace: str | None = Field(default=None, pattern=r'^[a-z0-9-]+$')

    @model_validator(mode="after")
    def require_address_source(self):
        """Reject an address with neither a known URL nor a configuration binding."""
        if self.base_url is None and self.base_url_property is None and self.internal_base_url is None and self.external_base_url is None:
            raise ValueError("A service address needs base_url or base_url_property")
        return self
