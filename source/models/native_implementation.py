"""Production Java only; contracts and dependency metadata are application-owned."""
from pydantic import BaseModel, ConfigDict, Field
from models.native_unit_bundle import NativeSourceFile


class NativeImplementation(BaseModel):
    """Implementation response for one configured unit, without tests or harness recipes."""
    model_config = ConfigDict(extra='forbid')
    files: list[NativeSourceFile] = Field(min_length=1)
    unresolved_questions: list[str] = Field(default_factory=list)
