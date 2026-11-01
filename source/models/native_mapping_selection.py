"""Small mapping-only response constrained to parsed native API choices."""
from pydantic import BaseModel, ConfigDict
from models.native_verification_binding import NativeVerificationBinding


class NativeMappingSelection(BaseModel):
    """No code, expected values or test generation is allowed in the mapping response."""
    model_config = ConfigDict(extra='forbid')
    binding: NativeVerificationBinding
