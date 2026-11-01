"""One parser-derived syntactic item; significance and equivalence are not inferred."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class ParserChecklistItem(BaseModel):
    """Retain original provenance, call candidates and statically resolved path certainty."""

    model_config = ConfigDict(extra='forbid')

    id: str
    code_node_id: str
    kind: Literal['literal', 'constant_reference', 'branch', 'call', 'write', 'exception', 'initialization']
    detail: str
    syntax_type: str
    source_identity: str
    source_hash: str
    source_file: str | None = None
    start_line: PositiveInt
    end_line: PositiveInt
    start_column: PositiveInt
    end_column: PositiveInt
    excerpt: str
    path_certainty: Literal['certain', 'uncertain']
    properties: dict[str, str] = Field(default_factory=dict)
    arguments: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
