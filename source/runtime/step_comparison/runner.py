"""Execute retained step scenarios using the existing comparison and boundary engines."""
from models.step_comparison_plan import StepComparisonPlan
from runtime.format_comparison.runner import run_comparison


def run_step_comparison(plan,profile,directory,*,tool=None):
    """Validate the step scope, then reuse JVM isolation, controls and observations."""
    verified=StepComparisonPlan.model_validate(plan.model_dump(mode='json'))
    return run_comparison(verified,profile,directory,tool=tool)
