# Metadata Checklist, Eping, Alternative 2

Status: implemented on `codex/metadata-2` and locally validated. Live trial deferred by explicit user instruction; do not resume the conversion run.
Date: 2026-10-31.

## Objective

Replace the single large metadata/checklist request with small, independently validated tasks. Generate known metadata deterministically, retain valid checklist mappings, and send precise corrections only for unfinished items. Preserve compilation, JUnit, original/native comparison and final operation acceptance.

## Implementation steps at a glance

1. Separate deterministic metadata, semantic metadata and checklist mapping.
2. Define narrow batch responses and structured validation errors.
3. Group checklist items by method and enforce request-size limits.
4. Select exact source evidence and allow bounded expansion.
5. Validate every returned item and collect all detectable errors.
6. Retain valid mappings and retry only rejected items.
7. Persist shared retry budgets and resumable item state.
8. Route implementation questions separately from citation repairs.
9. Assemble and validate the final metadata deterministically.
10. Replay saved failures, then test one complete operation.

## Problems addressed

| Problem | Required change |
| --- | --- |
| The entire checklist is assigned in one call. | Group items into small method-based batches. |
| Requests include excessive repeated evidence and instructions. | Use role-specific schemas and focused evidence selections. |
| Feedback does not identify the failing items. | Return item IDs, error codes, offending locations and expected corrections. |
| Validation stops at its first error. | Finish all independent checks that can safely run and return an aggregate report. |
| Every correction regenerates all metadata. | Request replacement entries only for rejected or unfinished IDs. |
| Several unrelated metadata duties share one call. | Separate contracts/bindings from checklist citation work. |
| Successful mappings lack independently retained state. | Persist mappings per item, with integrity and freshness information. |
| Metadata retries sometimes attempt to solve production defects. | Distinguish mapping errors, implementation concerns and tool limitations. |
| Repeated timeouts resend the same large task. | Split unfinished batches within durable total request budgets. |
| Citation completeness can be mistaken for equivalence. | Label mapping results as traceability only and retain all behavioral checks. |

## Scope and unchanged behavior

- Apply the shared mapping path to basic components, configured OP steps, format subtrees/partitions, whole configured formats and behavior units wherever they currently require parser checklist mappings.
- Keep the existing final bundle schemas and translate the retained results into their existing checklist fields.
- Do not recreate AI-written behavior facts or replace source evidence with AI summaries.
- Do not change Composer Mapper, Excel Generator, bank-demo Java/XML, operation ordering, dependency ownership, logging policy, model choice, API timeout or global context limit.
- Do not weaken exclusion authorization, source freshness, safe-path/API guards, compilation, executed-test requirements, original/native comparison or final assembly checks.
- Do not edit historical requests, responses, accepted artifacts or attempt counters.
- This plan does not itself fix the separate CCString production/test disagreement. It supplies the correct classification and correction route for such problems.

## Proposed flow

1. Freeze the compiled production sources and their parsed APIs.
2. Construct application-owned metadata from current source/configuration and accepted prerequisite records.
3. Obtain only the remaining semantic contract or binding choices in a separate bounded task, when they cannot be derived safely.
4. Plan and persist checklist batches against the frozen source and production revisions.
5. Request mappings for one batch using its focused evidence.
6. Validate every parseable response entry; retain independently valid entries.
7. Request repairs only for rejected or missing entries, or expand evidence when required.
8. Split oversized or repeatedly timed-out unfinished batches without resetting the shared budget.
9. Merge all current mappings into the existing metadata schema and run whole-result validation.
10. Continue the existing test and behavioral verification stages. Mapping completion alone never accepts a component, unit or operation.

## Detailed design

### 1. Assign one responsibility to each task

The application supplies exact component/unit IDs, configuration/source hashes, known dependencies, evidence identities, assigned packages and current prerequisite references. The native parser supplies actual public APIs, including inherited methods and declaring-type provenance.

The application must still select and validate which APIs belong to the target boundary. It must not export every helper simply because the parser found it. Ambiguous binding or contract decisions remain a separate focused task; they must not be guessed or mixed with checklist mapping.

Keep the existing DTO-contract structure stage and route-test stage distinct. Checklist batching must not turn these into code-generation jobs or introduce unnecessary calls for tasks with no checklist.

### 2. Use narrow response contracts

Define a batch envelope identifying its task revision, batch and production revision. Its entries contain a checklist item ID and either generated-code locations or a structured unresolved concern.

Use a list of entries so duplicate IDs remain detectable. A dictionary that silently overwrites duplicates is unsuitable. Valid item entries can contain several locations; one real excerpt may support several items. No one-to-one method-layout correspondence is required.

Code, Maven dependencies, whole contracts, tests and unrelated checklist IDs are forbidden in a mapping response. Do not request explanatory essays or the complete previous response.

Malformed JSON or an invalid envelope cannot produce accepted entries. For a valid envelope, validate entries independently so a malformed entry does not discard unrelated valid entries. Partial retention never means the whole task passed.

### 3. Plan deterministic, size-bounded batches

Start with a configurable target of 10-20 checklist items, default 15, grouped by original method and source identity. Preserve deterministic order. Item count is a target, not a guarantee that the request fits.

Measure the complete serialized request, including instructions, schema, selected evidence and correction payload. Use a dedicated metadata request ceiling below the existing global limit, initially 100,000 characters, with a configurable expected response allowance. Record UTF-8 bytes and decimal KB/MB/GB using the existing request-size logger. Characters/bytes are not token measurements.

Split before sending if either bound would be exceeded. Large methods may require multiple item batches. Persist parent/child batch lineage. A single item that cannot fit with sufficient evidence remains incomplete with a precise size/evidence diagnostic; never truncate it silently or mark it covered.

### 4. Select focused, exact evidence

Include the assigned checklist entries and their source references, original enclosing methods, relevant configuration, required declarations/constants and supporting definitions. Preserve exact text, source identities, hashes and line ranges.

Supply a compact application-generated index of candidate native types/methods and exact generated source excerpts sufficient for the mapping task. Original and generated methods need not share names or structure. Native evidence selection must not rely solely on matching their names.

Use parser-backed dependency relationships and the whole native symbol index for navigation. Allow a bounded request for additional exact methods/files when evidence is insufficient. Supply supporting setup, decorators, inherited methods and shared utilities when relevant; do not drop them merely because they live outside the enclosing method.

Maintain full evidence locally. A mapping cannot be accepted against unavailable evidence or a stale excerpt. If evidence selection is uncertain, expand it or report an evidence-selection limitation. Do not ask the model to invent behavior or cite code it was not shown.

### 5. Collect precise validation errors

Validate all independent entries before returning the report. Check envelope/revision, item identity, duplicate/unknown IDs, required locations, safe production paths, available source revisions and nonempty exact excerpts. Then report every missing assigned ID.

Errors identify the batch, item ID, code, offending field/path and required correction. Suggested codes include `missing_item`, `duplicate_item`, `unknown_item`, `stale_revision`, `missing_file`, `empty_excerpt`, `excerpt_not_found`, `malformed_entry` and `evidence_unavailable`.

Do not run dependent checks when their inputs are invalid. For example, a missing file yields `missing_file`; it does not also produce an invented excerpt mismatch. Infrastructure or parser failure remains a tooling problem, not hundreds of item defects.

Example feedback:

```json
{
  "batch_id": "batch-04",
  "accepted_item_ids": ["item-A"],
  "errors": [
    {"item_id": "item-B", "code": "missing_item", "action": "Return a mapping for this assigned item."},
    {"item_id": "item-C", "code": "excerpt_not_found", "path": "src/main/java/example/Mapper.java", "action": "Cite an exact excerpt from the supplied current file."}
  ],
  "requested_replacement_ids": ["item-B", "item-C"]
}
```

The example IDs and path are illustrative only and must never be copied into a real request as task data.

### 6. Retain successful items and make targeted repairs

Save valid mappings immediately after their checks. Correction calls contain only rejected/missing IDs, their precise errors, necessary evidence and the previous entries for those IDs. Accepted siblings are read-only and need not be regenerated.

Merge validated replacements in application code. Reject attempts to overwrite unrelated accepted items or inject entries belonging to another batch. Run a final exact-set check across the complete assigned checklist.

Bind retained items to their original source/configuration, generated production, evidence selection and validation-policy revisions. Initially invalidate all mappings affected by a changed production file; use finer method-level reuse only where dependency tracking proves it safe. Never carry a citation forward simply because the same text still appears in changed code.

### 7. Make progress and budgets durable

Persist batch plans, item states, evidence manifests, requests/responses, aggregate diagnostics, validated mappings and split lineage. States distinguish pending, mapped, needs correction, evidence incomplete, implementation concern and terminal failure. A mapped item is not an accepted unit.

Each item may participate in at most the configured correction-attempt limit, initially four. Also freeze a finite total logical-call and transport-attempt allowance for the original mapping task before execution. Account for initial batches, repair calls, evidence expansion and split children within that allowance.

Transport retries consume the transport allowance; any logical request consuming an item attempt must be recorded consistently. Rebatching, restarting, changing error text or creating child batch IDs cannot replenish budgets. Exhaustion stops only unfinished work with a clear report; completed item records remain reusable if current.

Do not automatically repeat the same oversized request four times. Preflight failures split immediately. After repeated timeouts, split only the unfinished work and only if budget remains. Persist configurable defaults and their accounting rules explicitly; tests must establish the upper bound on calls.

### 8. Route failures without guessing

- Missing/invalid citations return to checklist mapping.
- Insufficient supplied evidence returns to bounded evidence expansion.
- Parser, build environment and comparison limitations remain tooling diagnostics and do not trigger implementation correction.
- An AI statement that implementation is missing is a concern, not proof. Investigate it against the original source and generated implementation. A source-supported defect or an actual behavioral difference returns to the existing implementation correction stage with focused evidence.
- If production changes, recompile it and invalidate affected mappings/bindings/tests according to existing freshness rules. Preserve unrelated current work and all existing attempt accounting.
- Never resolve an implementation concern by changing expected outputs or inventing an automatic checklist exclusion. Existing authorized exclusions and comparison policies still govern.

### 9. Assemble existing metadata in application code

Combine deterministic fields, independently checked semantic metadata and current item mappings. Adapt basic/subtree mappings into `checklist_implementations`; adapt whole-format/unit answers into `checklist_answers` using their existing schemas and authorized exclusion semantics.

Run both aggregate mapping validation and existing owner validators. Every required item must be accounted for under existing policy. Correct batch citations must not bypass whole-result identities, typed interfaces, prerequisite ownership or freshness checks.

Keep three separate outcomes visible: traceability complete, technical checks passed, and observed original/native comparison passed. None independently proves exhaustive equivalence, and component success does not accept the full operation.

## Milestones and acceptance tests

### M1 — Contracts and aggregate diagnostics

Add narrow batch models and a validator returning all independent errors. Test mixed valid/invalid entries, all error codes, duplicates, malformed envelopes, safe paths and exact excerpts. Demonstrate that several different defects appear in one report while valid items survive.

### M2 — Batching and evidence selection

Implement stable method-based grouping and complete request measurement. Test large methods, one oversized item, reordered inputs, Unicode byte sizes, shared/inherited supporting definitions and bounded evidence expansion. No source summaries or silent truncation are allowed.

### M3 — Durable mappings and budgets

Add per-item storage, integrity checks and split lineage. Test interrupted execution, unchanged resume without new calls, stale source/code/policy invalidation, accepted-item protection and total-budget exhaustion across nested splits. Old task counters remain unchanged.

### M4 — Role separation and final assembly

Derive trusted metadata and actual APIs, isolate unresolved semantic choices, integrate batch mapping and assemble existing final schemas. Cover basic components, configured steps, format partitions and whole units. Verify that route tests and DTO-only tasks without checklists do not gain mapping calls.

### M5 — Corrections and operational reporting

Request repairs only for failed entries, classify implementation concerns and split timeout-prone batches within shared budgets. Test source-supported production correction, inconclusive concerns, tooling failure and regenerated-code invalidation. Logs show item/batch progress, request weights, role/call budgets and the actual blocking cause without exposing credentials.

### M6 — Saved-request replay and single-operation trial

Use read-only copies of the saved GetClientLinks request with 168 checklist items. Demonstrate bounded requests, exact-ID feedback, partial retention and no regeneration of accepted siblings through deterministic model fixtures. Run regression tests and the real JavaParser/build checks before live calls.

Then run the same single-operation selection, `INTERNET/GetClientLinksOp`, with all technical gates. Preserve original histories; use explicit current revisions and never reset an exhausted historical budget silently. Verify actual compilation, JUnit, original/native comparisons and final operation assembly. Report remaining blockers honestly, including the separate CCString concern if unresolved.

Stop after the single-operation trial for review before expanding to the full bank demo. No commit, push or deployment is implied by this plan.

## Expected files to change:

Paths marked **new** are proposed modules; final names may be tightened during implementation without unrelated restructuring.

- [metadata_checklist_batch.py](../../source/models/metadata_checklist_batch.py) — **new** batch/envelope and per-item response contracts.
- [metadata_checklist_validation.py](../../source/runtime/behavior_conversion/metadata_checklist_validation.py) — **new** aggregate entry validation and precise diagnostics.
- [metadata_checklist_batches.py](../../source/runtime/behavior_conversion/metadata_checklist_batches.py) — **new** stable batch planning, splitting and request-size bounds.
- [metadata_checklist_evidence.py](../../source/runtime/behavior_conversion/metadata_checklist_evidence.py) — **new** exact evidence manifests, selection and expansion.
- [metadata_checklist_state.py](../../source/tools/state_store_tools/metadata_checklist_state.py) — **new** durable per-item progress, integrity and shared budget accounting.
- [metadata_checklist.py](../../source/agents/behavior_conversion/metadata_checklist.py) — **new** focused mapping and repair instructions with clearly separated examples.
- [metadata_checklist.py](../../source/runtime/behavior_conversion/metadata_checklist.py) — **new** mapping orchestration, partial retention and final assembly adapter.
- [staged_metadata.py](../../source/models/staged_metadata.py) — separate semantic metadata from batched checklist fields while preserving final bundle schemas.
- [staged_pipeline.py](../../source/runtime/behavior_conversion/staged_pipeline.py) — integrate the new metadata stages into full conversion.
- [staged_conversion.py](../../source/runtime/behavior_conversion/staged_conversion.py) — integrate equivalent behavior in the isolated path where checklist answers are required.
- [staged_adapters.py](../../source/runtime/behavior_conversion/staged_adapters.py) — derive trusted metadata and consume aggregate mapping results.
- [staged_pipeline.py](../../source/agents/behavior_conversion/staged_pipeline.py) — remove checklist duties from general metadata instructions.
- [stage_tasks.py](../../source/runtime/behavior_conversion/stage_tasks.py) — connect durable batch budgets and classified retries to existing model transport.
- [staged_conversion_state.py](../../source/tools/state_store_tools/staged_conversion_state.py) — retain links to new mapping-task records without rewriting old attempts.
- [pipeline_configuration.py](../../source/models/pipeline_configuration.py) — add explicit batch-size, metadata-size and shared-budget settings.
- [native_metadata.py](../../source/runtime/behavior_conversion/native_metadata.py) — reuse parsed API/provenance indexes; extend only where focused evidence selection needs additional exact source ranges.
- [NativeApiInspection.java](../../source/behavior-verification-java/src/main/java/il/co/dcd/verification/NativeApiInspection.java) — extend method-range/index output only if existing parser evidence is insufficient.
- [verification_ladder.py](../../source/runtime/behavior_conversion/verification_ladder.py) — consume assembled answers and aggregate diagnostics while preserving final verification policy.
- [validation.py](../../source/runtime/component_conversion/validation.py) and [partition_validation.py](../../source/runtime/component_conversion/partition_validation.py) — share aggregate checklist checks in component/partition owner validation; preserve their build/comparison/acceptance duties.
- [test_metadata_checklist.py](../../source/tests/test_metadata_checklist.py) — **new** batch, evidence and aggregate validation tests.
- [test_metadata_checklist_state.py](../../source/tests/test_metadata_checklist_state.py) — **new** resume, integrity and non-resetting budget tests.
- [test_metadata_checklist_integration.py](../../source/tests/test_metadata_checklist_integration.py) — **new** saved-request and cross-path integration tests.
- [test_staged_pipeline.py](../../source/tests/test_staged_pipeline.py), [test_staged_conversion.py](../../source/tests/test_staged_conversion.py) and [test_behavior_verification_checklist.py](../../source/tests/test_behavior_verification_checklist.py) — regressions for shared stages and existing acceptance checks.
- [Component-first implementation plan](plans/Component-First%20Composer%20Conversion%20Implementation%20Plan.md) — record integration status and measured acceptance evidence.
- This document — track milestone decisions, actual changed files, test results and remaining limitations.

## Completion criteria

- No mapping call receives the full 168-item checklist when batching is required.
- Every correction identifies the exact unfinished IDs and all independently detectable errors.
- Valid mappings survive unrelated failures and unchanged resume.
- Total calls remain bounded across transport retries, repairs, evidence expansion and split children.
- Current source/API/ownership and exclusion rules still apply to assembled metadata.
- Successful citation validation is never reported as behavioral equivalence or full operation acceptance.
- The single-operation trial produces a complete final outcome report, including actual blockers when acceptance is not achieved.

## Implementation checkpoint — 2026-10-31

### Delivered behavior

- IDs, source provenance and parser-derived APIs are assembled locally. A separate semantic request selects owned API types/member IDs; it does not recreate signatures, hashes or checklist mappings.
- Components, configured steps, format partitions and staged whole-unit paths share the item controller where checklist answers are required. DTO-only and route-test tasks retain their existing roles. Configured formats still require their existing whole-unit answers and verification binding.
- Batches default to 15 items. Complete instructions, schema, evidence and feedback must fit the 100,000-character ceiling with 16,000 characters reserved for the response. Smaller global limits still apply.
- JavaParser supplies exact declaration ranges. A file-grouped catalog avoids repeated paths and advertises omitted evidence for bounded expansion. Structural items outside methods can use whole-source evidence. Initial native selection is a navigation aid, not proof of semantic relevance. Oversized evidence splits or remains incomplete; code is never silently truncated.
- Aggregate validation retains valid entries and reports independent missing, duplicate, unknown, malformed, unsafe and unavailable citations together. Whole-unit entries also pass existing AST and authorized-exclusion checks. Final owner validation remains required.
- Additive `metadata_checklist_*` tables persist mappings, integrity proofs, item states, batch lineage, full requests/responses and frozen logical/transport limits. Source/code/policy changes invalidate proofs. Splits, repairs and production changes do not reset budgets.
- Repairs request only unfinished IDs. Evidence gaps, tooling/provider failures and model implementation concerns receive separate diagnostics. A concern alone does not regenerate Java: independent batches continue, while unresolved concerns remain incomplete for source/behavior investigation. Actual interface defects and output differences retain the existing bounded implementation-correction route.
- Mapping completion remains traceability only. Typed boundaries, ownership, freshness, source guards, compilation, executed JUnit, original/native comparisons and operation assembly remain required.

### Changed files and responsibilities

- New [batch models](../source/models/metadata_checklist_batch.py), [mapping instructions](../source/agents/behavior_conversion/metadata_checklist.py), [aggregate validator](../source/runtime/behavior_conversion/metadata_checklist_validation.py), [batch planner](../source/runtime/behavior_conversion/metadata_checklist_batches.py), [evidence selector](../source/runtime/behavior_conversion/metadata_checklist_evidence.py), [controller](../source/runtime/behavior_conversion/metadata_checklist.py), [semantic assembler](../source/runtime/behavior_conversion/metadata_semantics.py) and [state module](../source/tools/state_store_tools/metadata_checklist_state.py) implement the separated responsibilities.
- [Configuration](../source/models/pipeline_configuration.py), [staged schemas](../source/models/staged_metadata.py), [stage tasks](../source/runtime/behavior_conversion/stage_tasks.py), [full stages](../source/runtime/behavior_conversion/staged_pipeline.py), [isolated stages](../source/runtime/behavior_conversion/staged_conversion.py) and [adapters](../source/runtime/behavior_conversion/staged_adapters.py) connect them to existing final bundle contracts.
- [Native metadata](../source/runtime/behavior_conversion/native_metadata.py), [Java inspection](../source/behavior-verification-java/src/main/java/il/co/dcd/verification/NativeApiInspection.java) and new [evidence ranges](../source/behavior-verification-java/src/main/java/il/co/dcd/verification/NativeEvidenceRanges.java) expose exact locations. Component [validation](../source/runtime/component_conversion/validation.py), partition [validation](../source/runtime/component_conversion/partition_validation.py) and [static checks](../source/tools/behavior_verification/static_checks.py) collect independent mapping errors while preserving final guards.
- New `test_metadata_checklist*.py` tests and focused changes to `test_staged_pipeline.py` and `test_behavior_static_checks.py` verify the implementation. This document and the component-first plan record results. Existing staged state tables and verification-ladder acceptance did not require modification.

### Local validation and limits

- The JavaParser tool rebuilt successfully with Java 25. The broader staged/isolated/side-road/mapping/static regression command passed **87 tests**. The latest focused batch/state/integration/saved-replay command passed **21 tests**. A separate real offline Maven/JUnit fixture passed with batched metadata and unchanged-source reuse. Counts overlap and are not summed.
- Read-only saved GetClientLinks replay: **168 items**, **13** fixture mapping requests including one single-item repair, largest batch **15**. JSON requests measured **54,924–82,597 characters**; instructions also fit within the reserved 84,000-character request bound. Separate semantic JSON measured **77,411 characters**. Unchanged replay reused all mappings without further calls.
- Measurements: [saved-request-replay.json](../outputs/metadata-2-local-validation-20261031/saved-request-replay.json). Fixture citations validate mechanics, not semantic coverage or behavioral equivalence. There were **zero provider calls**, historical database writes or counter resets.
- The M6 full-operation trial is intentionally **not run**, following the user's later instruction. No conversion process was resumed or monitor created. No operation acceptance, commit, push or deployment is claimed. The separate CCString issue remains outside this change.
- Mapper, Excel, bank-demo Java/XML, operation ordering, logging policy, model, API timeout and global context limit remain unchanged. Earlier uncommitted work was preserved; unrelated code was not modified by this implementation.
