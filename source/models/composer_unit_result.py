"""Preparation/execution outcomes remain separate from conversion acceptance."""
from typing import Literal
from pydantic import BaseModel,Field


class ComposerUnitResult(BaseModel):
    """Unavailable execution is diagnostic, never a successful comparison."""
    status: Literal['package_ready','preparation_unavailable','execution_completed','execution_unavailable']
    package: str|None=None
    issues: list[str]=Field(default_factory=list)
    observation: dict|None=None
