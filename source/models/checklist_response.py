"""Per-item generation answers; approvals and proof facts cannot arrive in this payload."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from models.checklist_code_location import ChecklistCodeLocation


class ChecklistResponse(BaseModel):
    """An answer names code, requests a checkable exclusion, or states an unresolved question."""
    model_config = ConfigDict(extra='forbid')
    checklist_id: str
    status: Literal['implemented', 'not_applicable', 'unresolved']
    locations: list[ChecklistCodeLocation] = Field(default_factory=list)
    reason: Literal['other_direction', 'branch_fixed_off', 'uncertain_target_not_selected', 'framework_plumbing', 'approved_exception'] | None = None
    rule_id: str | None = None
    approval_id: str | None = None
    question: str | None = None

    @model_validator(mode='after')
    def consistent_answer(self):
        if self.status == 'implemented' and (not self.locations or self.reason or self.question or self.rule_id or self.approval_id):
            raise ValueError('Implemented answers require only actual code locations')
        if self.status == 'not_applicable' and (self.locations or not self.reason or self.question):
            raise ValueError('Exclusions require a reason, without implementation locations or questions')
        if self.status == 'unresolved' and (self.locations or self.reason or self.rule_id or self.approval_id or not (self.question or '').strip()):
            raise ValueError('Unresolved answers require only a nonempty question')
        if self.reason == 'approved_exception' and (not self.approval_id or self.rule_id):
            raise ValueError('Explicit exceptions reference a separately stored approval')
        if self.reason != 'approved_exception' and self.approval_id:
            raise ValueError('Approval IDs are not proof for an automatic exclusion rule')
        return self
