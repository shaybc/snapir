# Prompt 32 — Feedback Loop Integration

## Context
Stage 8. All agents and the batch dispatcher exist.
This prompt adds the feedback routing that connects validation failures back
to the appropriate conversion or generation agent.

## Reference
`Implementation_plan_V8.md` section 7 (Mermaid control flow — feedback edges),
section 5 Phase 6 (`route_validation_failure`).

## Files to create
```
tools/routing_tools/feedback_router.py
```

## `feedback_router.py`

```python
class FeedbackRouter:
    """
    Routes validation failures back to the correct agent for re-processing.
    Each ValidationFailureClass maps to a specific feedback action.
    """

    def route(
        self,
        conn,
        report: ValidationReport,
        run_config: RunConfig
    ) -> FeedbackAction:
        """
        Returns a FeedbackAction describing what to re-run.

        build_failure:
          -> Re-run JavaServiceGenerationAgent for this operation.
          -> If fails again: set status=blocked, blocking_reason=compile_failed.

        conversion_gap:
          -> Identify which implClass produced the wrong logic.
          -> Re-run IbmJavaCleanerAgent for that implClass.
          -> Then re-run assembly (Phase 4) and generation (Phase 5).
          -> Then re-validate.

        equivalence_gap:
          -> Re-run JavaServiceGenerationAgent.
          -> Supply CodeEquivalenceReviewAgent output as additional instruction.

        shared_component_gap:
          -> Identify the shared component causing failures.
          -> Re-run IbmJavaCleanerAgent for the shared component.
          -> Invalidate all dependent operations (cascade_invalidation Rule 1/2).
          -> Re-run affected operations from Phase 3.

        routing_mismatch:
          -> Re-run StepImplementationInserterAgent pass 3 (execute method).
          -> Supply trace diff as additional instruction.
          -> Then re-run validation.

        validation_fixture_gap:
          -> Regenerate golden XML pairs and stub specs.
          -> Re-run validation only (no conversion changes).
          -> Cap at MAX_AGENT_TASK_RETRIES.
        """

    def apply_feedback(
        self,
        conn,
        action: FeedbackAction,
        run_config: RunConfig
    ) -> None:
        """Applies the feedback action: updates task statuses, queues re-runs."""
```

```python
class FeedbackAction:
    failure_class: ValidationFailureClass
    operation_id: str
    target_agent: str
    affected_artifact_ids: list[str]
    additional_instructions: str
    retry_count: int
```

## Feedback cap
Each feedback loop is capped at MAX_AGENT_TASK_RETRIES cycles.
After the cap: set operation status=needs_human_review,
blocking_reason=max_retries_exceeded.
Preserve the last failure evidence for the human reviewer.

## Tests
`tests/test_feedback_router.py`:
- routing_mismatch routes to StepImplementationInserterAgent pass 3.
- shared_component_gap triggers cascade_invalidation for dependents.
- MAX_RETRIES exceeded → needs_human_review.
- validation_fixture_gap does not re-run conversion agents.
