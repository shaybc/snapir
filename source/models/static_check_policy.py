"""Trusted checker policy; the candidate is never allowed to supply its own policy."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.tag_attribute_contract import TagAttributeContract


class StaticCheckPolicy(BaseModel):
    """Only duplicate metadata markers are preapproved plumbing; behavior items remain mandatory."""
    model_config = ConfigDict(extra='forbid')
    plumbing_rules: list[Literal['implicit_constructor_marker', 'configured_setup_marker', 'throws_declaration_metadata']] = Field(
        default_factory=lambda: ['implicit_constructor_marker', 'configured_setup_marker', 'throws_declaration_metadata'])
    tag_contracts: list[TagAttributeContract] = Field(default_factory=list)
    schema_version: Literal['static-check-policy-v1'] = 'static-check-policy-v1'
