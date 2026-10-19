"""One named operation-step object supplied to the assembled service."""

from pydantic import BaseModel, ConfigDict, Field


class OperationDependency(BaseModel):
    """Bind a configured step to a typed constructor argument and service field."""

    model_config = ConfigDict(extra="forbid")
    binding_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    type_name: str = Field(min_length=1)
    parameter_name: str = Field(pattern=r"^[A-Za-z_$][\w$]*$")
    field_name: str = Field(pattern=r"^[A-Za-z_$][\w$]*$")
