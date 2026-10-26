"""An effective formatter occurrence retaining its original source position."""

from pydantic import Field
from models.common_models.common import SnapirBaseModel


class ScopedFormatNode(SnapirBaseModel):
    """Preserve repeated fields, nested ownership, attributes, and attached decorators."""

    occurrence_id: str
    definition_id: str
    source_selector: str
    tag: str
    attributes: dict[str, str] = Field(default_factory=dict)
    collection_kind: str = 'keyed'
    java_class: str | None = None
    decorators: list[dict] = Field(default_factory=list)
    reference_definition_id: str | None = None
    children: list['ScopedFormatNode'] = Field(default_factory=list)
