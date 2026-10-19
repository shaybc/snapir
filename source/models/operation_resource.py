"""A runtime resource supplied to accepted steps through their existing input contract."""

from pydantic import BaseModel, ConfigDict, Field


class OperationResource(BaseModel):
    """Describe a configured provider and the input value it creates per execution."""

    model_config = ConfigDict(extra="forbid")
    input_key: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    parameter_name: str = Field(pattern=r"^[A-Za-z_$][\w$]*$")
    field_name: str = Field(pattern=r"^[A-Za-z_$][\w$]*$")
    connection_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    transaction_scope: str | None = Field(default=None, exclude_if=lambda value: value is None)
