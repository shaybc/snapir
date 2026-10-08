"""One source input checked by closure and consumed by conversion scheduling."""

from typing import Literal
from pydantic import BaseModel


class ConversionComponent(BaseModel):
    """Preserve a source identity and hash together with its originating configuration."""

    kind: Literal["ibm_java", "xml_context", "xml_fmtdef"]
    logical_id: str
    source_file: str | None = None
    source_hash: str
    source_content: str
    shared: bool = False
    origin: str = ""
