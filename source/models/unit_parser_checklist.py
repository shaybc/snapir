"""Source-bound parser inventory, kept separate from conversion acceptance."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from models.parser_checklist_item import ParserChecklistItem


class UnitParserChecklist(BaseModel):
    """An extracted inventory can coexist with incomplete call resolution and unrun verification."""

    model_config = ConfigDict(extra='forbid')

    source_manifest_hash: str
    configuration_hash: str
    status: Literal['extracted', 'verification_incomplete', 'not_run'] = 'not_run'
    reachability_status: Literal['analyzed', 'verification_incomplete', 'not_run'] = 'not_run'
    items: list[ParserChecklistItem] = Field(default_factory=list)
    fact_scope: Literal['complete_unit','basic_element'] = 'complete_unit'
    composition_code_nodes: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    verification_status: Literal['not_run'] = 'not_run'
    acceptance_gate_enabled: Literal[False] = False
    schema_version: Literal['parser-checklist-v1'] = 'parser-checklist-v1'
