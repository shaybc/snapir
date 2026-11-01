"""Source-linked observable obligations, independent of generated implementation style."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class BehaviorCitation(BaseModel):
    """Identify an exact excerpt in a verified source revision or agreed policy."""
    model_config = ConfigDict(extra='forbid')
    identity: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class BehaviorFact(BaseModel):
    """Describe a conditional observable outcome; the runtime assigns its stable ID."""
    model_config = ConfigDict(extra='forbid')
    fact_id: str = ''
    origin: Literal['source', 'compatibility_policy'] = 'source'
    behavior: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    evidence: list[BehaviorCitation] = Field(min_length=1)
