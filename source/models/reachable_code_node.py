"""Source-backed executable and initialization locations in a conservative slice."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, PositiveInt


class ReachableCodeNode(BaseModel):
    """Keep precise provenance without claiming that this body executed at runtime."""

    model_config = ConfigDict(extra='forbid')

    id: str
    kind: Literal['method', 'constructor', 'implicit_constructor', 'static_initializer',
                  'instance_initializer', 'static_field_initializer', 'instance_field_initializer',
                  'static_field_default', 'instance_field_default']
    declaring_class: str
    signature: str
    source_identity: str
    source_hash: str
    source_file: str | None = None
    start_line: PositiveInt
    end_line: PositiveInt
    start_column: PositiveInt
    end_column: PositiveInt
    excerpt: str
    path_certainty: Literal['certain', 'uncertain'] = 'uncertain'
    initialization_rule: Literal['java_default_value'] | None = None
    default_value: str | None = None
