"""Identify a Java implementation independently of its consumers and current content."""

from pydantic import BaseModel, ConfigDict


class SourceImplementationRecord(BaseModel):
    """Describe the originating source class; method signatures are optional exact selectors."""

    model_config = ConfigDict(extra="forbid")
    implementation_id: str
    workspace_id: str
    source_root: str
    source_path: str
    package_name: str
    class_name: str
    method_signature: str | None = None
    source_hash: str

