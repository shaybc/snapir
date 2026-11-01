"""One approved framework Tag reader contract, never a per-formatter behavior catalog."""
from pydantic import BaseModel, ConfigDict, Field


class TagAttributeContract(BaseModel):
    """Pin a pure nullable lookup over the stable configured initialization-attribute snapshot."""
    model_config = ConfigDict(extra='forbid')
    contract_id: str = Field(min_length=1)
    tag_class: str
    source_hash: str
    getter: str = 'getAttribute'
