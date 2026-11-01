"""A restricted executable bridge plan, never arbitrary adapter source or expected answers."""
from pydantic import BaseModel,ConfigDict,model_validator
from models.native_verification_binding import NativeVerificationBinding


class NativeExecutableAdapter(BaseModel):
    """The converter executes validated native calls and captures their actual observations."""
    model_config=ConfigDict(extra='forbid')
    binding:NativeVerificationBinding | None = None
    limitation:str | None = None

    @model_validator(mode='after')
    def require_plan_or_limitation(self):
        """A missing capability is explicit and cannot masquerade as an executable plan."""
        if self.limitation is not None and not self.limitation.strip():raise ValueError('Limitation must be nonblank')
        if (self.binding is None)==(self.limitation is None):
            raise ValueError('Return exactly one binding or a nonblank limitation')
        return self
