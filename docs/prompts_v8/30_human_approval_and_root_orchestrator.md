# Prompt 30 — `HumanApprovalAgent` + `RootMigrationOrchestratorAgent`

## Context
Stage 8. All agents and tools from Prompts 01-29 exist.
These two agents wire the entire pipeline together.

## Reference
`Implementation_plan_V8.md` sections 5 (all phases), 6 (agent roster),
7 (control flow Mermaid diagram).

## Files to create
```
agents/root_migration_orchestrator/
├── __init__.py
└── agent.py
agents/human_approval/
├── __init__.py
└── agent.py
```

## `HumanApprovalAgent`

Presents gate reports and waits for operator input.
In V1: reads from stdin. Future: web UI or Slack integration.

```python
class HumanApprovalAgent:
    """
    Presents a gate report and blocks until operator approves or rejects.
    On approve: returns True, orchestrator continues.
    On reject: returns False, orchestrator stops the run.
    On timeout (if configured): auto-reject with log.
    """

    def present_gate(
        self,
        gate_number: int,
        report: str,
        run_id: str
    ) -> bool:
        """
        Prints the report to console.
        Writes to human_review_items table.
        Reads 'yes'/'no' from stdin.
        Logs decision to runs table.
        Returns True for yes, False for no.
        """
```

## `RootMigrationOrchestratorAgent`

The top-level SequentialAgent that runs all phases in order.

```python
from google.adk.agents import SequentialAgent

root_migration_orchestrator = SequentialAgent(
    name="RootMigrationOrchestratorAgent",
    description="Orchestrates the full WSBCC migration pipeline.",
    sub_agents=[
        legacy_composer_analysis_agent,     # Phase 1
        context_hierarchy_phase,            # Phase 1 post-processing
        migration_planning_agent,           # Phase 1 planning
        gate1_approval,                     # Human Gate 1
        closure_phase,                      # Phase 2
        conversion_phase,                   # Phase 3
        gate2_approval,                     # Human Gate 2
        assembly_phase,                     # Phase 4
        gate3_approval,                     # Human Gate 3
        generation_phase,                   # Phase 5
        validation_phase,                   # Phase 6
        manifest_phase,                     # Phase 7
        documentation_phase,                # Phase 8
        gate4_approval,                     # Human Gate 4
    ]
)
```

## Phase wrappers
Each "phase" above is a function that returns a SequentialAgent or parallel
agent group appropriate for that phase:

```python
def build_conversion_phase(run_config: RunConfig) -> SequentialAgent:
    """
    For each operation batch:
      assert_closure_ready for all operations in batch
      run IbmJavaCleanerAgent for all ibm_java in batch closures
      run XmlToJavaConverterAgent for all xml_fmtdef in batch closures
      run ContextToJavaConverterAgent for all context in batch closures
      run NativeJavaReviewAgent for all converted
      check common-lib for promotion opportunities
    """

def build_assembly_phase(run_config: RunConfig) -> SequentialAgent:
    """
    For each READY operation:
      build_routing_plan
      build_context_plan
      build_serialization_plan
      run ServiceSkeletonGeneratorAgent
      run StepImplementationInserterAgent (6 passes)
      run OperationEquivalenceReviewAgent
    """
```

## Batch processing loop
```python
def process_batch(
    conn,
    batch: MigrationBatch,
    run_config: RunConfig,
    phase: str
) -> BatchResult:
    """
    Processes one batch through the given phase.
    Tracks progress in agent_tasks table.
    Returns BatchResult with success_count, failed_count, blocked_count.
    On any blocking failure: pause batch, log, continue with next batch.
    """
```

## Run resumption
On startup with `--resume run_id`:
1. Load RunConfig from DB.
2. Find the current phase from runs.current_phase.
3. Find all agent_tasks with status=needs_rerun or status=pending.
4. Resume from the earliest incomplete task.

## Tests
`tests/test_root_orchestrator.py`:
- Gate 1 rejection stops the run.
- Batch with one blocked operation continues processing others.
- Resume finds correct restart point after simulated crash.
