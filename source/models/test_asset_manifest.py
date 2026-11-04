"""Immutable execution identity for separately generated fixture and scenario files."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class TestAssetManifest(BaseModel):
    """Content hashes bind test receipts to exact source, code, policy and runtime."""
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['test-assets-v1'] = 'test-assets-v1'
    boundary_identity: str
    revision: str
    context_hash: str
    files: dict[str, str]

