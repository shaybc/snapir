"""Bind a resolved entry method to its original declaration and source revision."""

from pydantic import BaseModel, ConfigDict, PositiveInt


class LegacyBoundaryMethod(BaseModel):
    """Source-backed method location, not a statement of behavioral equivalence."""

    model_config = ConfigDict(extra='forbid')

    implementation_class: str
    declaring_class: str
    signature: str
    return_type: str
    source_identity: str
    source_hash: str
    source_file: str | None = None
    start_line: PositiveInt
    end_line: PositiveInt
    excerpt: str
