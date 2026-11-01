"""A deterministic call/initialization edge with explicit candidate uncertainty."""

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class ReachableCallEdge(BaseModel):
    """Empty from_id denotes configured setup, rather than an invented source call site."""

    model_config = ConfigDict(extra='forbid')

    id: str
    from_id: str
    kind: str
    declared_target: str
    candidates: list[str] = Field(default_factory=list)
    uncertain: bool
    unbounded: bool
    reason: str
    source_identity: str | None = None
    source_hash: str | None = None
    source_file: str | None = None
    start_line: PositiveInt | None = None
    end_line: PositiveInt | None = None
    start_column: PositiveInt | None = None
    end_column: PositiveInt | None = None
    excerpt: str = ''
