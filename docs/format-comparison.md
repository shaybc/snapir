# Format execution diagnostics

This opt-in facility executes real Composer and saved native Java using the existing
generic adapters. It does not replace checklist validation, change acceptance, regenerate
Java, reset attempts, or resume a conversion. No format-name-specific adapter is used.

For a standalone test without fact generation, add `--no-facts`. This skips parser
checklist collection and fact-derived branch probes while retaining entry discovery,
reachability, source hashes, compilation and actual execution. Standalone comparisons
never run AI fact mapping or use fact validation as a blocking gate. Reports explicitly
record `fact_collection=disabled_for_test`, `fact_validation=not_run` and
`fact_validation_blocking=false`. Normal converter fact collection and gates remain
unchanged. The input profile file is not rewritten.

## Separate converter experiment without facts

`bank-demo/getclientlinks-facts-disabled-test.json` is a separate test profile copied
from the saved GetClientLinks settings. It selects
`executable_verification.experimental_disable_facts=true` and a new sibling output
root. It does not modify or resume the existing run. Compilation, actual JUnit,
source/configuration freshness, APIs, settings, dependencies and chain checks remain.
Parser fact collection and AI fact mapping are not performed. Static settings/API
analysis remains enabled independently of parser facts.

The setting is accepted only with explicit `conversion_checklist_v1` mode. Its policy
and component reuse namespace differ from normal conversion. Unit proofs and operation
records are labeled `experimental_only`, with verification version
`conversion-facts-experiment-v1`; normal unit/operation receipt checks reject them.
Progress reporting never promotes an experiment to normal `acceptance_complete`.
The profile also enables wrapper diagnostics with fact collection disabled.

To create another isolated profile without starting any work:

```powershell
python -B -m tools.behavior_verification.create_fact_experiment --source normal-profile.json --destination experiment-profile.json --output-root C:/experiments/new-run
```

Use a fresh run/output namespace. Do not use the experimental profile to resume the
existing conversion database. The profile generator refuses overlapping output roots.

## Explicit standalone execution

Set `PYTHONPATH=source` and use the project's Python environment:

```powershell
python -B -m tools.behavior_verification.format_comparison --plan plan.json --profile profile.json --enable
```

The command writes a disposable execution directory and prints the report path. Pass
`--output` to select a new empty directory. Exit zero means all planned comparisons
matched without unavailable/failed cases; it does not mean exhaustive equivalence.

Add `--discover-context --windows-user-key` to make a bounded discovery request using
the configured model key from the Windows current-user environment. Credentials are
not written to requests or reports. Context discovery failure remains visible and
dependent cases are unavailable rather than silently running with invented values.

## Plans and generic bindings

`FormatComparisonPlan` contains `original_unit`, `native_sources`, `entries`, `cases`,
and `discovery`. `original_unit` uses the existing resolved unit/configuration format.
`runtime.format_comparison.planning.original_unit` can create a standalone unit from
hashed original sources and an implementing configuration root. Use `scope=basic`
only for an undecorated root without children; otherwise select `scope=configured`.

Each named entry selects a direction and `NativeVerificationBinding`. Constructor
arguments and setters may use `source=configuration,key=dataName`. Format arguments
may read `source=context,key=runtime.channel`; unformat arguments use `source=xml`.
`@configuration:dataName` selects an exact context/projection key from configuration.
Select exact Java parameter types to resolve overloads. Do not use executable expressions.

For unformat, project an actual result or argument value with `context_writes`; this
maps public return/getter values to the original logical context keys. Missing fields
and null remain distinct. The harness does not infer a missing value from a default.

Each `FormatComparisonCase` selects `binding_id`, initial context, XML, optional root
configuration attributes, and required input identities. `intentionally_absent` marks
deliberate absence tests. `roundtrip_binding_id` runs the selected unformat entry on
each side's actual format output, in fresh JVMs. Never preformat collection rows in
an adapter. Invoke the production composition that owns the transformation.

## AI-assisted preparation

`prepare_plan` consumes current original evidence, saved native sources, baseline
fixtures and existing bindings. If an explicit model callable is supplied, it discovers
runtime inputs and can propose missing bindings from actual native API declarations.
AI returns declarative metadata only. Source-backed values need exact citations;
exploratory values stay labeled exploratory. Dynamic keys, missing helpers and ambiguous
inputs remain unresolved. Existing bindings are preferred to an AI proposal.

Fixture expansion overlays source-backed or exploratory values on supplied baselines.
It does not claim that all combinations are reachable, infer expected outputs, or
silently discard cases above the configured budget. Targeted branch IDs are marked
observed only when matching original runtime probes are present.

## Optional future conversion runs

`format_comparison.enabled` defaults to false. Explicitly enabling it adds post-build
diagnostics for complete configured formats after their normal checks pass. It uses
the existing controlled input generator and bounded AI input/binding preparation.
Unsupported dependencies, wiring or observations produce diagnostic limitations.
The current conversion policy, checklist gates and component acceptance stay unchanged.
This setting does not start a conversion; an operator must separately start one.

## Results and limitations

`format-comparison.json` retains the plan hash, tool hash, raw observations, fixtures,
unresolved inputs and counts. `format-comparison.md` provides a short checklist.
Each case is matched, different, comparison_unavailable or execution_failed.
XML is compared exactly and structurally without trimming text or reordering children.
Exception classes are compared; messages are retained and optionally compared. Internal
Context write counts do not have to match native local assignments. Partial state on
exceptions is explicitly not established by the current observer.

These are local observations, not a correctness percentage or a proof of equivalence.
External-service/database support requires explicit controlled dependencies; the runner
does not create live connections or invent external responses.

## Implementation file map

| File | Why it changed or was added |
| --- | --- |
| `models/format_comparison_settings.py` | Independent, disabled-by-default execution policy and budgets. |
| `models/format_comparison_plan.py` | Basic/configured scope and exact directional entry selection. |
| `models/format_comparison_case.py` | Safe fixture identities, intentional absence and round-trip metadata. |
| `models/format_context_requirement.py` | Source citations, branch values and unresolved runtime requirements. |
| `models/pipeline_configuration.py` | Exposes the separate opt-in policy. |
| `models/native_boundary_value.py` | Permits exact configuration-attribute inputs. |
| `models/native_verification_binding.py` | Describes configuration setters without executable adapter code. |
| `agents/behavior_conversion/format_context_discovery.py` | Bounded discovery and metadata-only binding instructions. |
| `runtime/format_comparison/context_discovery.py` | Validates and retains AI evidence and uncertainty. |
| `runtime/format_comparison/planning.py` | Resolves hashed source/configuration snapshots through existing analysis. |
| `runtime/format_comparison/bindings.py` | Restricts recipes, resolves configured keys and reports missing inputs. |
| `runtime/format_comparison/cases.py` | Expands branch fixtures without invented expected results. |
| `runtime/format_comparison/preparation.py` | Prefers existing metadata and retains unavailable preparation results. |
| `runtime/format_comparison/execution.py` | Reuses compilation and fresh-JVM execution. |
| `runtime/format_comparison/runner.py` | Coordinates diagnostics and preserves immutable snapshots. |
| `runtime/format_comparison/reporting.py` | Compares observations and writes truthful JSON/Markdown summaries. |
| `runtime/format_comparison/component_diagnostics.py` | Optional post-build integration, isolated from acceptance. |
| `runtime/format_comparison/__init__.py` | Declares the diagnostic package. |
| `runtime/behavior_conversion/verification_binding.py` | Validates the additional configuration recipes. |
| `runtime/component_conversion/validation.py` | Calls diagnostics only when explicitly enabled after normal checks. |
| `tools/behavior_verification/format_comparison.py` | Standalone command with explicit execution authorization. |
| `tools/behavior_verification/boundary_execution.py` | Preserves CR characters in source transport and retains process logs. |
| `harness/LegacyBoundaryAdapter.java` | Distinguishes context setup failure from formatter behavior. |
| `harness/TypedBoundaryAdapter.java` | Wires configuration and checks actual generic argument shapes. |
| `harness/NativeBoundaryValues.java` | Passes configuration/collection inputs without business transformations. |
| `harness/BoundaryHarness.java` | Retains bounded exception cause chains. |
| `tests/test_format_context_discovery.py` | Exercises citations, fixtures, unknown paths and request limits. |
| `tests/test_format_comparison_bindings.py` | Checks restricted wiring, disabled defaults and unchanged policy. |
| `tests/test_format_comparison_preparation.py` | Checks AI preparation and failure isolation. |
| `tests/test_format_comparison_reporting.py` | Checks presence, XML, exceptions and unavailable counts. |
| `tests/test_format_comparison_execution.py` | Executes channel, string and structured-collection examples in real JVMs. |

All Python paths in this table are relative to `source/`; Java harness paths are
relative to `source/behavior-verification-java/src/main/java/il/co/dcd/verification/`.
This document records the new diagnostic facility only, not unrelated workspace changes.
