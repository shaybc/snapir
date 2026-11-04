"""Immutable identity and file integrity for an original-code execution package."""
from pydantic import BaseModel,ConfigDict
from typing import Literal


class ComposerUnitManifest(BaseModel):
    """Hashes bind the complete package to discovered originals and selected runtime."""
    model_config=ConfigDict(extra='forbid')
    version: Literal['composer-unit-v1']='composer-unit-v1'
    identity: str
    files: dict[str,str]
    originals: dict[str,str]
