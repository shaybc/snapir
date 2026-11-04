"""Configured-step comparison uses the same isolated execution protocol as formats."""
from pydantic import model_validator
from models.format_comparison_plan import FormatComparisonPlan


class StepComparisonPlan(FormatComparisonPlan):
    """Restrict this plan to whole-step execution, never full operation routing."""
    @model_validator(mode='after')
    def configured_step_only(self):
        if self.original_unit.get('kind')!='configured_step' or any(e.direction!='step_execute' for e in self.entries.values()):
            raise ValueError('Step comparison requires explicit configured-step execution')
        return self
