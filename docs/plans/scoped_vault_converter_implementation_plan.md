# Schema-three Composer converter implementation plan

Status: C0–C5 intake, qualified access, closure inspection, contextual workflow preparation, and qualified reuse/invalidation implemented locally; C6 normal scoped startup and C7 bank-demo preparation fixes are implemented and verified locally. All 10 demo operation contexts prepare. C8 adds opt-in qualified native behavior-unit generation through both runtime entry points. C9 remains bank-wide acceptance and controlled enablement. Preparation-only remains the default; existing approvals and finalization evidence remain required.

Milestone numbering correction: references to the former "C6 end-to-end acceptance" in historical milestone notes or existing guard messages refer to the remaining C8 integration and C9 acceptance work below. They do not mean that only testing remains.

Updated: 2026-10-25. Mapper baseline: `7ee3a8945df449f7de181f9fe019383512e43a8b`.

## Outcome and boundaries

Bring the converter up to date with the working Composer Mapper and Excel generators. Consume schema-three vaults without copying inherited XML definitions into every channel, losing repeated steps, selecting the wrong format, or reusing conversion results from a different execution context.

Canonical notes describe source evidence. Manifest `operation_contexts` describe execution under a consuming channel. A canonical XML operation can execute in several channels with different overrides, selected steps, dependencies, and calls. Those executions share source notes but require distinct contextual bindings.

This plan supersedes earlier assumptions that every consuming channel receives its own copied operation and resource notes. It does not redesign the Mapper or Excel generators, change public endpoint naming, introduce Mapper resume, migrate old runs automatically, or authorize unrelated refactoring. Preserve legacy behavior and existing converter checkpoint policies.

## Mapper changes and converter obligations

| Current Mapper/output behavior | Required converter behavior |
| --- | --- |
| Manifest schema `3`, identity version `1` | Validate supported versions explicitly and persist the actual version. Do not simply remove the schema-three guard. |
| One canonical note per surviving source definition | Treat note paths as evidence locations, not executable channel identities. |
| `operation_contexts` identify consuming-channel execution | Import contexts and their selected references, ordered steps, entry, transitions, Java resolution, and calls. |
| XML is an implicit base for every other channel | Honor selected local overrides and inherited bindings for every channel. Do not add every XML operation to every channel or search arbitrary channels for a replacement. |
| Only referenced inherited operations are visited transitively | Convert the selected dependency closure. Missing requested contexts require evidence, not fabricated XML-default contexts. |
| Shared resources stay in their source inventory; inline resources retain operation ownership | Resolve qualified definitions and roles through contextual bindings, not global names or guessed folders. |
| Repeated and capitalization-variant step labels receive occurrence paths | Preserve every selected occurrence, original spelling, source position, effective order, parameters, and transitions. |
| Canonical step positions differ from filtered execution positions | Use ordered context `step_notes`; retain canonical source positions for traceability. |
| Named transitions use current-inclusive, case-sensitive forward search, then wrap | Preserve resolved occurrence targets, self-jumps, and backward jumps; `next` advances and `end` terminates. |
| Keyed wrappers replace earlier same-key children; indexed wrappers preserve repeats | Apply the collection policy within the correct parent scope and retain decorators and references. |
| Same-ID sibling root `fmtDef` definitions use last-wins | Use the selected definition as a whole. Do not compare content, keep both as executable definitions, or invent precedence across unrelated files. |
| Nested definitions preserve parent scope and occurrence selectors | Carry manifest identities and selectors rather than reconstructing identity from filenames. |
| Java notes represent candidates, including unresolved classpath evidence | Prove the selected source/binary origin before conversion; a unique FQCN candidate alone is insufficient. |
| Source hashes and note hashes have different purposes | Preserve source revision, source identity, rendered evidence, and contextual binding fingerprints separately. |
| Manifest publication streams through a temporary file | Require a completed manifest; import and hash incrementally without rebuilding a giant JSON string or redundant inventory copies. |
| Literal `#` and `%` remain in filesystem paths; Markdown links are escaped | Treat manifest paths literally. Decode legacy Markdown destinations once through the shared link parser, retaining vault-boundary checks. |
| Java reading supports strict UTF-8 with Windows-1255 fallback | Match that evidence-reading behavior without changing bytes, byte hashes, or source-size guards. |

Indexed wrapper names, confirmed by the user, are exactly:

- `AmtaIColl`
- `CCIColl`
- `ICollFEditQry`
- `ICollFEditQryWEB`
- `IndexedCollectionFormatHolder`
- `IndexedCollectionToFormat`
- `IndexedCollFormat`
- `IColl`
- `ICollSetLength`
- `IndexCollectionFormatDLS`
- `IndexCollectionFormatDLSWEB`
- `CCIndexedCollectionFormat`

All other wrappers use keyed behavior. The replacement key is the direct child's explicit `id`, otherwise `dataName`, otherwise `name`, with exact matching; unnamed children remain. `refFmt` and `refFormat` are references, not definitions to deduplicate by `refId`. PS10 XML wrappers use keyed behavior. See the [Composer manual](../comp-manual/wsbcc_developer_manual_v2.md) and [current vault contract](../scoped_vaults.md).

## Confirmed converter gaps

- Workspace intake still invokes `--out` and validates the legacy analysis registry. Scoped generation uses `--vault` and a completed manifest.
- The manifest reader supports explicit shared-vault access, but the converter importer still takes the guarded path and its scoped persistence is built around schema two.
- Scoped import derives operations from canonical entity rows, does not persist execution contexts, hardcodes schema two, and hashes the complete manifest with `read_bytes()`.
- Closure building, channel filtering, resource resolution, and several runner/checkpoint paths still query artifacts by bare logical name.
- Routing dictionaries and call-site membership use step labels, collapsing repeated occurrences. Return-body switches are merged across steps.
- Format/decorator maps and context persistence use names that cannot distinguish separate parents, owners, or execution bindings.
- Contract planning assumes operation-owned format rows and uses the default manifest-reader path. Shared canonical resources require contextual role resolution.
- Reuse and invalidation can select by logical name and source hash without enough contextual evidence. Existing channel-qualified call graph keys should be preserved.

## Target identity and persistence contract

Keep five concepts distinct:

1. **Source definition:** workspace, kind, definition ID, source channel, relative source path, selector, and revision/hash.
2. **Execution context:** run plus manifest operation identity, consuming channel, operation name, canonical operation definition, and canonical note path.
3. **Selected binding:** execution context plus resource role/reference or call-site occurrence, pointing to the selected qualified definition.
4. **Step occurrence:** canonical step note/selector and source position, with its effective execution position and resolved targets in a context.
5. **Conversion result:** implementation identity and configuration/binding fingerprint, including verified Java origin, dependency revisions, policy versions, and accepted contracts.

Mapper IDs and converter component IDs use different algorithms. Bridge them through verified coordinates and source revisions; do not assume digest equality or merge definitions merely because their bytes match. Canonical `usage_id` is not automatically an execution binding.

Retain existing source-definition and canonical-usage storage. Plan additive tables for `scoped_operation_contexts` (run/context identity, unique channel/name), `scoped_context_bindings` (context plus binding role/occurrence), and `scoped_channel_evidence` (channel mapping/configuration snapshot). Qualify closure, context hierarchy, field inventory, task, and result records where needed. Final columns and migration SQL are a C0 deliverable, not a broad schema rewrite.

Channel mapping notes are not necessarily hashed manifest entities. Snapshot the mapping and source-root/profile evidence used by conversion. A canonical note's default formatter, decorator, parent, or routing annotations must not silently override consuming-context selections. Where current output lacks necessary contextual proof, report a precise contract gap and propose a separate narrow Mapper addition before generating behavior.

## C0 — Freeze the contract and audit consumers

First-milestone audit: intake enters through `workspace_intake.py` and `vault_importer.py`; schema-two import remains isolated in `scoped_vault_importer.py`. Schema-three import uses additive context/binding tables and the new access API. Existing closure, filtering, resource, contract, checkpoint, runner, reuse, and invalidation call sites listed below still need C3–C5 migration. No legacy bare-name table receives canonical schema-three artifacts, and schema-three intake does not invoke the existing contract planner.

Stored channel notes include import-chain/tag evidence. Configured origin settings and source coordinates are snapshotted, but source relocation, source revision, and loaded Java classpath remain explicitly unverified. Canonical formatter/decorator/context annotations remain source defaults; qualified closure work must resolve missing consuming-context proof before enablement. Mapper and converter identity digests are not treated as interchangeable.

- [x] Create representative schema-three fixtures and retain legacy/schema-two compatibility fixtures.
- [x] Audit bare-name queries, direct folder assumptions, operation lookups before closure construction, and every downstream consumer of routing/format/context models.
- [x] Define typed references, execution contexts, occurrences, additive persistence, and the Mapper-to-converter identity bridge.
- [x] Document coverage and missing-evidence rules for channel mappings, local overrides, Java origins, source relocation, formatter/decorator bindings, and context parents.
- [x] Record exact files and migration impact for each following increment before editing its code.

Gate: reviewed input/access contract and acceptance fixtures. Existing scoped conversion guard remains active.

## C1 — Schema-aware intake and scalable import

- [x] Detect manifest-based vaults before requiring legacy `analysis/channel-operation-registry.md`; retain legacy checks for legacy inputs.
- [x] Correct Mapper invocation to `--vault`; pass configured scoped layout and a stable workspace ID when scoped generation is requested. Preserve fresh-output/source safety and avoid an unapproved default-mode change.
- [x] Select executable operations from emitted contexts. Keep source XML dependencies available through canonical references even when filtering consuming channels.
- [x] Persist actual schema/identity versions, parsed note evidence, source definitions, execution contexts, selected bindings, and diagnostics separately. Inventory-only definitions must not become executable roots.
- [x] Snapshot channel mappings, configured source root, definition revision hashes, classpath/profile settings, and proof status. Keep source relocation and loaded-origin verification explicitly pending C3.
- [x] Hash/import incrementally, remove whole-manifest byte loading and avoid redundant full inventory/parsed-note copies. Batch database writes and publish import readiness only after validation completes.
- [x] Reject incomplete generation markers, corrupt references/hashes, unsafe paths, unsupported versions, and interrupted imports. Preserve the previous valid run.
- [x] Add bounded timestamped import progress, counts, elapsed time, and failure summaries without claiming conversion readiness or an unsupported ETA.

Gate: correct, inspectable inventory and execution-context persistence on large inputs; conversion remains blocked.

## C2 — Qualified converter access

- [x] Introduce one scoped access API requiring run and execution context for operation, step, resource, and call-site lookups.
- [x] Return qualified objects containing business labels and evidence paths. Do not populate a global legacy table with an arbitrary same-name winner or mutate a shared view when switching channels.
- [x] Preserve canonical source positions and selected effective order; excluded `onlyFor` steps remain inventory but cannot enter the execution closure.
- [x] Use literal manifest paths, including `#` and `%`. Use the established parser only for legacy Markdown/wiki links, with exact-file lookup before fragment handling and one decode.
- [x] Preserve supported legacy/schema-two adapters explicitly. Do not infer missing schema-three contexts from source defaults.

Gate: identical names across channels, owners, parents, and occurrences are independently retrievable. C0–C2 form the first deliverable, with the generation guard intact.

## C3 — Qualified closures, routing, and resource semantics

- [x] Build closures from selected contextual references and ordered step occurrences, not inventory enumeration or label sets.
- [x] Use context entry and transition targets. Cross-check `onlyFor` and verified Composer lookup semantics without rebuilding routes from canonical default annotations.
- [x] Store return-body switches per step occurrence and return code, retaining different format bindings on repeated steps.
- [x] Resolve format roles, return-body formats, transitive references, decorator chains, and context parents through qualified bindings. Visit definitions by qualified identity and preserve existing semantic cycle checks.
- [x] Apply keyed replacement and indexed ordering at each actual parent. Preserve nested definition ownership, unnamed children, reference occurrences, and attached decorators. Replace name-only decorator keys where they collapse indexed children.
- [x] Qualify context hierarchy and field-inventory persistence so equal names with different selected parents/overrides cannot overwrite each other.
- [x] Require verified Java source/binary origin using source roots, dependencies, and profile. Retain unresolved-classpath diagnostics and existing external-component policy.
- [x] Add strict UTF-8 then Windows-1255 fallback to audited Java evidence reads, preserving original bytes/hashes and existing size limits.
- [x] Separate vault corruption from operation-specific unresolved evidence. Block affected operations and dependent callers; unrelated inventory must not falsely block every conversion.

Gate: closures preserve runtime behavior and contain only actual dependencies, with complete traceability and actionable unresolved evidence.

### C3 implementation boundary and changed files

`build_scoped_operation_closure` is an explicit inspection entry point. It returns `evidence_ready` or `blocked` with `conversion_enabled=false`; it never writes a legacy `READY` operation closure. The existing `build_operation_closure` still rejects scoped conversion. Missing source revisions, bindings, origin profiles, tags, parents, or named targets remain blockers rather than guessed replacements.

Selected XML is verified against original byte hashes and exact selectors. `fmtDef` remains a definition container; the actual body wrapper determines collection behavior. Nested definitions retain qualified source identities. Return-body switches and routes remain keyed by step occurrence. Only reachable called contexts are analyzed, and their unresolved evidence propagates to callers; operation-call cycles alone do not become context-parent or step-routing errors. C4 must still implement coordinated call contracts.

Java analysis requires an explicit production project and resolved classpath profile. It checks captured source coordinates/revisions and competing origins, applies the existing replacement/retention policy, verifies retained/platform archive entries, and reuses the complete syntax dependency checker. Syntax-discovered helpers may use canonical inventory only after project visibility and exact captured coordinates are established. A unique Mapper candidate alone is insufficient. This establishes scoped static evidence, not compiler attribution or runtime equivalence; C6 retains those acceptance gates.

Changed files and purposes:

- [Scoped closure model](../../source/models/scoped_operation_closure.py) and [format occurrence model](../../source/models/scoped_format_node.py): preserve qualified analysis, disabled conversion, nested ownership, attributes, and occurrence-specific decorators.
- [Closure entry point](../../source/tools/conversion_tools/closure_builder_tool.py): expose scoped inspection without changing the legacy conversion path.
- [Builder](../../source/tools/conversion_tools/scoped_closure/builder.py) and [package](../../source/tools/conversion_tools/scoped_closure/__init__.py): assemble reachable contextual evidence and propagate blockers.
- [Routing](../../source/tools/conversion_tools/scoped_closure/routing.py): cross-check source selection, positions, entry, exact-case targets, and per-occurrence switches.
- [Source verification](../../source/tools/conversion_tools/scoped_closure/source_evidence.py): verify source bytes and selectors; retain original child ordinals.
- [Collection policy](../../source/tools/conversion_tools/scoped_closure/collection_policy.py) and [formats](../../source/tools/conversion_tools/scoped_closure/formats.py): preserve the twelve indexed wrappers, keyed replacement, references, nested identities, and attached decorators.
- [Contexts](../../source/tools/conversion_tools/scoped_closure/contexts.py): resolve qualified ancestry, cycles, fields, and provenance.
- [Java origins](../../source/tools/conversion_tools/scoped_closure/java_origins.py) and [dependency bridge](../../source/tools/conversion_tools/scoped_closure/java_dependencies.py): prove selected profile origins and reuse syntax-level dependency validation.
- [Analysis persistence](../../source/tools/conversion_tools/scoped_closure/state.py): add `scoped_operation_closures`, `scoped_context_hierarchies`, and source-coordinate indexes without changing legacy tables.
- [Qualified access](../../source/tools/composer_mapper_tools/scoped_vault_access.py): read channel snapshots, canonical steps, nested definitions, and exact Java source coordinates.
- [Java decoder](../../source/tools/java_analysis_tools/java_text.py) and [guarded reader](../../source/tools/java_analysis_tools/java_source_reader.py): share strict UTF-8/Windows-1255 decoding, optional expected-byte-hash checks, and existing size limits.
- [Source discovery](../../source/tools/source_discovery_tools/discovery.py), [import classification](../../source/tools/source_discovery_tools/dependencies.py), [dependency checker](../../source/tools/conversion_tools/java_dependency_readiness.py), and [JDK syntax scanner](../../source/tools/java_analysis_tools/source_dependencies/SourceReferenceScanner.java): keep the audited Java evidence path encoding-compatible without editing source bytes or executing workspace code.
- [Scoped closure tests](../../source/tests/test_scoped_closure.py), [vault guide](../scoped_vaults.md), and this plan: verify the milestone and document its boundaries.

Contracts, generation runners, component reuse, invalidation, Mapper output, Excel generators, and unrelated local work remain unchanged by C3.

## C4 — Contracts, calls, conversion units, and runners

- [x] Reuse the existing qualified call graph. Bind calls to step occurrences and manifest-selected target contexts; do not introduce a second arbitrary cross-channel resolver.
- [x] Plan request/response contracts from contextual format roles and canonical definitions. Preserve public endpoint naming, published-contract readiness, and approved external reuse policy.
- [x] Handle excluded dependencies through the existing inclusion/published-contract workflow or an explicit blocker. Never silently omit a dependency or automatically convert excluded operations.
- [x] Move checkpoint, behavior runner, assembly runner, and unit-builder preparation reads onto qualified access; remove bare-name prerequisites in those paths only as required.
- [x] Share verified canonical implementation excerpts by definition/revision during preparation, while retaining independent configured units for different parameters, routes, bindings, and contracts. Accepted-code reuse remains C5.
- [x] Carry occurrence identities through prepared generation and route-test inputs. Keep original business names in diagnostics and existing valid Java/public naming policies.
- [x] Preserve timeout/error priorities, initialization, side effects, return-body switching, final steps, and direct Java-call requirements in the prepared evidence and workflow requirements.
- [x] Preserve coordinated-contract handling for operation-call cycles. Backward/self step transitions are routing behavior, not operation-call dependency cycles.

Gate: both runtime paths receive correct contextual contracts and units, without declaring discovery alone to be conversion readiness.

### C4 implementation and verification

`prepare_scoped_workflow` uses existing call discovery against the unchanged intake manifest, then builds local qualified evidence for each explicitly selected execution context. It distinguishes opaque manifest execution identities from public `channel/operation` keys. Calls retain canonical step occurrence identities and manifest target contexts. Calls to omitted services require a single pinned XML API; competing application pins, missing contracts, unsupported strategies, and operation-call cycles remain explicit blockers. Existing intake-plan runs retain their publish-before-caller policy. Pinned boundaries do not require callee source inspection, and excluded operations are never scheduled implicitly.

Contracts retain the existing escaped endpoint/base-URL naming policy and planned/assembled/validated state rules. Their format bodies and transitive references come from contextual roles, including local overrides, selected root definitions, indexed children, and attached decorators. An unchanged fingerprint preserves prior contract state; changed evidence returns it to planned. This is contract planning, not publication.

Each selected step and format direction has an independent configured unit, including response formatters referenced only by return-body switches. Every selected switch binds to an actual response unit. Canonical source excerpts are cached only by definition and verified revision; configured identities additionally include consuming context, occurrence, routes, format bindings, Java origins, external policies, and call contracts. Raw XML remains provenance; `effective_configuration` and effective trees carry the selected collection semantics. Service-connection decisions reuse the existing resolver with the explicit project/classpath and no internal commit. Unverified supporting sources and unresolved connection facts block preparation rather than adding unchecked code.

Checkpoint, behavior runner, and assembly runner now enter a shared preparation path before bare-name lookups, model calls, component gates, or builds. It persists `scoped_workflow_preparations` and writes `scoped_workflow_preparation.json` in the dependency-closure report folder. Behavior, assembly, and route-test payloads retain occurrence identities, source/effective positions, operation attributes, initialization/side-effect requirements, timeout/error priority, body switches, native-call requirements, and final steps. The runtime stops at `conversion_scoped_gated`; all payloads retain `conversion_enabled=false`. No native code or accepted conversion artifacts are produced by C4. C5 reuse/invalidation and C6 real generation/review/compilation/behavior acceptance remain required.

Expected files changed for C4 and why:

- [Scoped configured unit](../../source/models/scoped_configured_unit.py): carry qualified occurrence identity and effective configuration without changing legacy unit models.
- [Contracts](../../source/tools/conversion_tools/scoped_workflow/contracts.py), [calls](../../source/tools/conversion_tools/scoped_workflow/calls.py), [units](../../source/tools/conversion_tools/scoped_workflow/units.py), [connections](../../source/tools/conversion_tools/scoped_workflow/connections.py), [payloads](../../source/tools/conversion_tools/scoped_workflow/payloads.py), [preparation](../../source/tools/conversion_tools/scoped_workflow/preparation.py), and [package](../../source/tools/conversion_tools/scoped_workflow/__init__.py): keep each preparation responsibility focused.
- [Closure entry](../../source/tools/conversion_tools/closure_builder_tool.py) and [scoped builder](../../source/tools/conversion_tools/scoped_closure/builder.py): allow explicit local-analysis boundaries while retaining default reachable inspection.
- [Unit entry](../../source/tools/conversion_tools/behavior_unit_builder.py): dispatch scoped inputs before legacy READY/name checks.
- [Profile](../../source/models/pipeline_configuration.py): add optional `scoped_java_project`; no implicit project inference.
- [Runtime adapter](../../source/runtime/scoped_conversion.py), [checkpoint](../../source/runtime/checkpoints.py), [behavior runner](../../source/runtime/behavior_conversion/runner.py), [assembly runner](../../source/runtime/operation_assembly/runner.py), and [report location](../../source/runtime/workflow_stages.py): publish preparation evidence and stop at the existing controlled-enablement boundary.
- [Connection evidence](../../source/runtime/behavior_conversion/service_connection_evidence.py): accept an explicit analysis profile and nonpersisting preparation without changing legacy defaults or ownership/decision rules.
- [Workflow tests](../../source/tests/test_scoped_workflow.py), [vault guide](../scoped_vaults.md), and this plan: document and check the milestone and remaining gates.

Mapper, Excel generators, legacy conversion output, existing public Java/API naming, and unrelated local changes remain unchanged by C4.

Verification: 14 scoped-workflow tests, 25 qualified-closure tests, 98 existing unit/call/behavior/assembly regressions, and 7 existing service-connection tests passed. These are deterministic preparation and compatibility checks; they do not establish C6 native end-to-end readiness or enterprise-scale performance.

## C5 — Reuse, invalidation, and checkpoint safety

- [x] Audit component, configuration, task, result, and native-artifact keys. Preserve already qualified keys; extend only keys that can collide.
- [x] Fingerprint qualified definitions/revisions, selected dependencies, consuming-context bindings, verified Java origins, contracts, and applicable schema/strategy/policy versions.
- [x] Invalidate actual qualified consumers: shared XML changes affect dependent contexts; a local override affects contexts selecting that override. Respect file-level hash granularity and invalidate conservatively where evidence cannot distinguish finer changes.
- [x] Reject stale checkpoint reuse after changed mappings, steps, references, source roots, classpath, or overrides until explicit refresh/replanning completes.
- [x] Use additive migrations and preserve old runs and artifacts. Do not add a new resume engine or silently reinterpret existing runs under schema three.

Gate: safe reuse is demonstrated for shared implementations, and unsafe reuse across distinct configurations is prevented.

### C5 implementation and verification

The existing behavior snapshot key `(run_id, category, identity)`, behavior-attempt fingerprint key, and assembly snapshot key `(run_id, operation_id, channel)` remain unchanged. Their scopes are sufficient when their identities are qualified. Legacy conversion/native rows can contain bare logical IDs, so schema-three work does not read them as compatible results. The generation entry explicitly retains the scoped conversion guard before any legacy accepted-snapshot compatibility lookup. Scoped task/result/native-output adapter identities hash the consuming context, configured unit, category, and local identity. No old task, result, artifact, or output file is migrated or removed.

Intake now records registry bytes, per-channel XML membership, and Java project metadata in its existing evidence snapshot. C5 checkpoints add the actual imported bindings, selected canonical definitions/usages, canonical/channel note revisions, source-file and verified archive revisions, source-project/classpath structure, source/vault/output roots, selection and schema settings, contextual contracts, pinned API decisions, and versioned conversion/testing/replacement policies. Credentials are not stored in checkpoint policy records; relevant settings/documents/archives are hashed. Root schema/identity versions and workspace identities remain explicit.

`scoped_checkpoints`, `scoped_reuse_entries`, `scoped_reuse_consumers`, and `scoped_stale_evidence` are additive tables. Canonical source excerpts share entries only by qualified definition, byte revision, policy, classpath, and source origin. Configured units retain independent identities for their consuming context, occurrence, routes, selected formats, calls, and policies. Prepared workflows reuse their complete checked evidence only after current-input validation; unchanged contexts skip closure rebuilding. Public endpoint and business labels are unchanged.

Changes invalidate the actual saved consuming contexts and their non-published callers. Pinned published APIs remain boundaries rather than inheriting callee implementation dependencies. A local override file affects its selected consumers; shared source changes affect shared consumers. File hashes deliberately invalidate all selected definitions from a changed physical file. Registry/import-chain changes invalidate dependent channels; source-project/classpath structure and connection-decision changes are conservative where the available evidence cannot prove a smaller scope. Stale status is sticky, resets affected service-contract readiness to planned, and preserves original evidence, outputs, and artifacts. Restoring bytes does not silently reaccept prior work.

Native-output adapters require an exact current context/unit fingerprint, an existing validator, intact payload/file-manifest metadata, and output files inside the run output root. They recheck inputs after validation and verify output bytes on each reuse. These adapters are exercised with deterministic validator/output fixtures; C5 does not generate native code, prove compiler/review acceptance, or enable the C6 runtime path.

The existing runtime reports stale contexts at `conversion_scoped_stale` before planning, rebuilding, or model calls. Inputs from pre-C5 scoped runs lack the required proof and require explicit fresh intake/replanning. There is no new resume engine or in-place schema reinterpretation. Preserve the old vault/database/generated files; regenerate changed source into a new vault and start a new run. Policy-only changes may use a still-current completed vault in a new run, subject to source/origin checks.

Files changed for C5 and why:

- [Checkpoint model](../../source/models/scoped_checkpoint.py): represent one qualified consumer's input proof and configured units.
- [Fingerprints](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py), [input evidence](../../source/tools/conversion_tools/scoped_reuse/evidence.py), [checkpoint verification](../../source/tools/conversion_tools/scoped_reuse/checkpoint.py), [state](../../source/tools/conversion_tools/scoped_reuse/state.py), [artifact adapters](../../source/tools/conversion_tools/scoped_reuse/artifacts.py), and [package](../../source/tools/conversion_tools/scoped_reuse/__init__.py): separate policy identity, source evidence, invalidation, additive persistence, and reuse validation.
- [Intake snapshot](../../source/tools/composer_mapper_tools/scoped_intake_evidence.py): capture registry/layout proof before first preparation.
- [Workflow preparation](../../source/tools/conversion_tools/scoped_workflow/preparation.py): check freshness before reuse and publish proof only after final input verification.
- [Unit builder](../../source/tools/conversion_tools/scoped_workflow/units.py): include C5 schema and conversion policy in configured-unit identity.
- [Runtime preparation](../../source/runtime/scoped_conversion.py): report affected stale contexts without rebuilding them.
- [Generation entry](../../source/runtime/behavior_conversion/generation.py): prevent schema-three work from falling through legacy accepted-result compatibility.
- [Reuse tests](../../source/tests/test_scoped_reuse.py), [workflow tests](../../source/tests/test_scoped_workflow.py), [vault guide](../scoped_vaults.md), and this plan: check the milestone and document the required refresh boundaries.

Mapper output, Excel generators, legacy schemas/keys/conversion behavior, and unrelated local work remain unchanged. C6 acceptance and enterprise-scale measurement are still required before generation is enabled.

Verification: 25 scoped-reuse cases, 14 scoped-workflow cases, 25 qualified-closure cases, and 120 existing conversion/runtime/service-connection/intake checks passed. Output-cache acceptance uses explicit fixture validators; no enterprise or native end-to-end readiness is inferred from these checks.

## Corrected remaining implementation sequence

The former C6 combined unfinished implementation with acceptance. Preparation-only tests and reports did not complete generation integration. Proceed through the following milestones in order; a passing intake must not imply native conversion readiness.

### C6 — Normal scoped startup

- [x] Add persisted `mapper_vault_layout: legacy | scoped` to the project profile, retaining the legacy default. Scoped generation requires an explicit nonblank `source_workspace_id`.
- [x] Reuse one Mapper command builder in normal startup and standalone intake. Forward scoped layout, workspace identity and Markdown mode; preserve existing legacy channel filtering. Behavior-unit startup must map all available channels so dependencies are not excluded by a source-channel filter.
- [x] Persist the real configuration/profile and import the generated schema-three vault normally. Stop at `scoped_inventory_ready` before legacy context/planning readers; normal resume must reach qualified preparation using the saved run.
- [x] Verify configuration validation, legacy command compatibility, source/vault output safety, a real scoped startup/resume fixture, and fresh bank-demo startup.

Gate: normal startup produces and imports schema three without a custom test harness or legacy bare-name planning. Generation remains disabled.

Verification (2026-10-25): 56 scoped-startup, standalone-intake, configuration, and operation-preflight tests passed. The real start/resume test launches the Mapper and verifies persisted schema/workspace identity, consuming-channel selection, Resume-menu discovery, source preservation, and the retained generation guard. Fresh normal `python -m cli start`, `resume`, and `status` commands against bank-demo are saved under `outputs/bank-demo-scoped-startup-20261025`. Startup generated schema three with 139 definitions and 10 contexts, paused at `scoped_inventory_ready`, and resume reached qualified preparation (`conversion_scoped_gated`, 0/10 prepared). C7 blockers remain; no native generation occurred. The legacy startup command and subprocess failure behavior are retained.

Broader CLI/model-readiness suites also reported failures in unchanged areas: missing `prompt_toolkit`, missing `configs/bank_demo.yaml`, outdated bank-demo operation-list expectations, and verbose diagnostic traceback expectations. Those tests are not reported as green and are outside this scoped-startup change. The temporary missing-JAR regression introduced while sharing command construction was corrected and the operation-preflight suite now passes.

### C7 — Resolve demonstrated bank-demo preparation blockers

- [x] Inspect ambiguous contexts against exact root/operation-local selectors and registration order. Fix a resolver defect only with source-backed precedence; if the demo itself duplicates a declaration incorrectly, document and correct that fixture separately.
- [x] Trace `on*Return="ErrorBody"` through operation format aliases and canonical bindings. Establish whether it is an alias, a missing demo declaration, or an unsupported construct before changing resolution.
- [x] Represent each consuming Java project's declared visibility of XML framework sources. Do not make all workspace classes globally visible or silently choose a source candidate. Preserve per-context origin proofs and invalidation.
- [x] Resolve framework format/decorator implementations using documented replacement behavior or proven source/library origins; preserve meaningful behavior rather than accepting empty stubs.
- [x] Resolve wildcard JDK imports and dependency review obligations with exact class inventory, preserving unresolved nonplatform dependency checks.
- [x] Rerun actual bank-demo mapping/intake/preparation from a fresh folder, with regressions proving that ambiguity, absent evidence and unsupported dependencies still block.

Gate: each supported demo operation has verified prepared inputs; any remaining unsupported operation has a specific documented blocker. Do not suppress diagnostics to make the demo green.

#### C7 implementation — 2026-10-25

The six original operation XML files declared the same contexts as their loaded `defaultFile/dsecontext.xml`, and their `ErrorBody` switch targets named no definition. Corrected only those fixture declarations/references: contexts remain in the channel default files and switches use the declared shared `StandardErrorRSFmt`. Mapper ambiguity and format-resolution rules were not relaxed, and no production precedence was inferred from these fixture duplicates.

The demo contains the shared framework implementations; its missing project metadata hid them from explicit Java profiles. Added three `.classpath` files: INTERNET references XML; IVR references XML and INTERNET for its common helpers; XML owns its source root. Added exact `scoped_java_projects` selection with the existing single-project fallback, used in closure preparation and service evidence. Qualified origin resolution can use an exact captured coordinate after proving explicit project visibility, class uniqueness, original source hash and guarded reads. It still rejects undeclared/ambiguous origins. C5 fingerprints now include the channel-project map and its selected project structures; policy version is `scoped-v3-c7-v1`, requiring fresh runs for old proofs.

A scoped-only helper recognizes uniquely indexed JDK package wildcards, while the existing full syntax dependency gate still checks actual type sites. Missing packages, competing class origins and unknown used types remain blockers. Legacy import classification is unchanged.

Further fresh-run evidence exposed absent service documents registered by the demo and internal operation dispatch misclassified as an external resource. Added the four registered XML/INTERNET service/connector documents, registering only the existing dummy fraud service and no fabricated URLs, credentials or database pools. For verified `CCComplexOpStep` operation-call boundaries, service inspection excludes the replaced dispatcher implementation while retaining its original conversion source. Genuine external lookups remain checked.

Expected files to change for this milestone (all necessary for the evidenced preparation blockers):

- [Profile](../../source/models/pipeline_configuration.py), [project selector](../../source/tools/conversion_tools/scoped_workflow/source_project.py), [preparation](../../source/tools/conversion_tools/scoped_workflow/preparation.py), and [connections](../../source/tools/conversion_tools/scoped_workflow/connections.py): channel-specific origin selection and operation-dispatch/service distinction.
- [Java origins](../../source/tools/conversion_tools/scoped_closure/java_origins.py), [platform imports](../../source/tools/conversion_tools/scoped_closure/platform_imports.py), and [qualified access documentation](../../source/tools/composer_mapper_tools/scoped_vault_access.py): verified source coordinates and scoped JDK wildcard handling.
- [Checkpoint](../../source/tools/conversion_tools/scoped_reuse/checkpoint.py) and [fingerprints](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py): invalidate reuse when channel/project policy or selected source structure changes.
- [INTERNET metadata](../../bank-demo/composer/Workspace/WSBCC_INTERNET/.classpath), [IVR metadata](../../bank-demo/composer/Workspace/WSBCC_IVR/.classpath), and [XML metadata](../../bank-demo/composer/Workspace/WSBCC_XML/.classpath): explicit demo source/project visibility.
- INTERNET [GetClientAccounts](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientAccounts.xml>), [GetAccountDetails](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetAccountDetails.xml>), [TransferFunds](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml>), [GetClientLinks](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml>); IVR [GetClientAccounts](<../../bank-demo/composer/Workspace/WSBCC_IVR/src/Xml Definition/Channel/IVR/selfDefOper/GetClientAccounts.xml>) and [GetAccountBalance](<../../bank-demo/composer/Workspace/WSBCC_IVR/src/Xml Definition/Channel/IVR/selfDefOper/GetAccountBalance.xml>): only duplicate context declarations and unresolved error-body target names change.
- XML [services](<../../bank-demo/composer/Workspace/WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dsedata.xml>) and [connectors](<../../bank-demo/composer/Workspace/WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseConnector.tmp>), INTERNET [services](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsedata.xml>) and [connectors](<../../bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dseConnector.tmp>): supply already-registered demo configuration documents and the existing dummy service instance.
- [Validation profile](../../bank-demo/scoped_converter_validation.yaml), [C7 tests](../../source/tests/test_scoped_c7.py), [demo README](../../bank-demo/README.md), [vault guide](../scoped_vaults.md), and this plan: reproducible input, positive/negative checks and accurate support boundaries.

Fresh normal startup/resume evidence: `outputs/bank-demo-c7-validation/bank-demo-c7-final`, from a new schema-three mapping and new database. All 10 selected contexts prepared successfully; 133 surviving source definitions remain after removing six duplicate fixture contexts. Preparation took 46.13 seconds in this demo run. Existing embedded framework replacement contracts remain documented evidence for unavailable framework types; no ad hoc replacement rules or source stubs were introduced. The runtime correctly remains `conversion_scoped_gated` with native generation disabled. C8/C9 are not complete.

Verification: 14 C7 tests and 71 existing qualified closure, workflow, reuse/invalidation and source-discovery cases passed across the focused/regression runs (85 distinct checks). The service adapter's existing minimal closure input remains supported. New negative checks retain unresolved actual type failures under JDK wildcard imports, reject competing source/library origins and empty project selections, and preserve genuine external-service failures when operation-dispatch evidence is excluded. The real bank-demo test remaps a fresh source copy and checks all 10 contexts, source-byte preservation, declared project visibility, and retained native-generation guards. No Mapper or Excel implementation was changed.

### C8 — Qualified native conversion integration

- [x] Adapt C4 prepared payloads/units to existing behavior generation and assembly entry points; retain execution identity, ordered occurrence bindings, selected formats, return-body units, context and Java provenance.
- [x] Preserve existing unit/operation review, compiler validators, constructor injection checks, external service contracts, published-callee ordering and human gates. Generate route scenarios from qualified resolved targets, including backward/self routes and terminal paths.
- [x] Bind task/result/native artifact reuse to C5 context/unit checkpoints and output hashes. Reject legacy bare-name accepted-result compatibility for schema three. Recheck input freshness before generation, acceptance and reuse.
- [x] Extend persisted planning and resume stages to reach generation, review, assembly, build/test and finalization for explicitly supported profiles. Keep unsupported strategy/profile combinations blocked.
- [x] Add real scoped native generation/review/compilation/executable behavior acceptance for both runtime paths. Offline model fixtures may supply deterministic candidate code, but compiler/build/test execution must be real and fixture limitations explicit.

Gate: a complete supported native path, with durable qualified evidence and existing approvals, works before any scoped guard is narrowed. Preparation success alone never authorizes conversion.

### Expected files to change:

First implementation step (C6):

- [Profile model](../../source/models/pipeline_configuration.py): additive layout selection and workspace-ID validation.
- [Mapper generation settings](../../source/tools/workspace_intake_tools/mapper_generation.py): shared command construction with output validation retained.
- [Pipeline startup](../../source/runtime/pipeline_runner.py): forward settings, persist workspace identity, and dispatch imported scoped inventory before legacy readers.
- [Standalone intake](../../source/workspace_intake.py): reuse the same command builder without changing its existing invocation behavior.
- [CLI run discovery](../../source/cli/discovery.py): show supported scoped checkpoints in the Resume menu.
- [Scoped startup tests](../../source/tests/test_scoped_startup.py): legacy/default/configuration/safety and real start/resume coverage.
- [Vault guide](../scoped_vaults.md) and this plan: explain actual support and remaining gates.

Subsequent implementation targets, to confirm against each blocker before editing:

- [Context analysis](../../source/tools/conversion_tools/scoped_closure/contexts.py), [format analysis](../../source/tools/conversion_tools/scoped_closure/formats.py), [qualified access](../../source/tools/composer_mapper_tools/scoped_vault_access.py), [Java origins](../../source/tools/conversion_tools/scoped_closure/java_origins.py), [source discovery](../../source/tools/source_discovery_tools/discovery.py), and [Java dependencies](../../source/tools/conversion_tools/scoped_closure/java_dependencies.py): C7 evidence-backed fixes only.
- [Prepared payloads](../../source/tools/conversion_tools/scoped_workflow/payloads.py), [scoped runtime](../../source/runtime/scoped_conversion.py), [checkpoint resume](../../source/runtime/checkpoints.py), [behavior runner](../../source/runtime/behavior_conversion/runner.py), [generation](../../source/runtime/behavior_conversion/generation.py), [service flow](../../source/runtime/behavior_conversion/service_flow.py), [assembly runner](../../source/runtime/operation_assembly/runner.py), and [qualified reuse](../../source/tools/conversion_tools/scoped_reuse/artifacts.py): C8 integration with existing gates, validators and persistence.

Mapper/Excel and demo-source changes are not presumed necessary. Any evidenced contract or demo defect requires its own minimal change and regression. Existing legacy paths, old runs and unrelated local changes remain untouched.

## C9 — Acceptance and controlled enablement

- [ ] Run the acceptance matrix below with deterministic fixtures and existing converter regressions; run relevant Mapper and Excel discovery regressions for shared-reader changes.
- [ ] Exercise real scoped conversion through generation, review, compilation, and behavior checks for both behavior and assembly runtime paths. Parser/unit tests alone do not establish end-to-end readiness.
- [ ] Measure mapping/import/conversion memory, elapsed time, progress, and entity/context counts on the user-designated bank demo. Enterprise input is unavailable locally; record demo scale explicitly and make no enterprise performance claim.
- [ ] Document supported schema/profile combinations, migration procedure, operational checks, and rollback.
- [ ] Lift the scoped-conversion guard only for a complete, verified capability path. Keep unsupported combinations explicitly blocked.

Gate: reviewed end-to-end evidence and deployable instructions. Retain previous compatible binaries, vaults, and database snapshots for rollback; do not mix old state with a newly interpreted vault.

### Historical C6 progress — preparation measurement only

The runtime now writes a separate `scoped_acceptance.json` alongside the preparation report. It records preparation elapsed time, UTC completion time, process lifetime peak RSS (explicitly labelled; unavailable counters are null with a reason), run-scoped inventory/context/binding counts, and prepared/blocked/reused context counts. Existing logging receives preparation start/completion events. This avoids allocation tracing overhead and does not claim to measure import, native conversion, or a preparation-only memory peak.

No capability guard is lifted. Both behavior and assembly still stop after qualified preparation. Real native generation, review, compilation, executable behavior checks, and the complete acceptance matrix remain required; C6 is **not complete**. The report records unmet gates explicitly even when preparation passes. The user designated the bank demo as the available local validation input; enterprise measurements are unavailable and must not be inferred from this demo run.

Files changed for this partial step: [acceptance measurement](../../source/runtime/scoped_acceptance.py), [runtime preparation](../../source/runtime/scoped_conversion.py), [report location](../../source/runtime/workflow_stages.py), [acceptance tests](../../source/tests/test_scoped_acceptance.py), this plan, and the [vault guide](../scoped_vaults.md). Mapper output, Excel, existing conversion guards, legacy execution, and unrelated local work remain unchanged.

Verification: 10 acceptance-report tests, 39 scoped workflow/reuse tests, and 43 existing behavior/assembly runtime tests passed (92 distinct tests). Existing runtime tests use offline model/build fixtures; this result does not establish real scoped native compilation or enterprise acceptance. No shared reader changed in this partial step, so Mapper/Excel regressions were not rerun.

### Fresh bank-demo validation — 2026-10-25

At the user's direction, compiled the current Mapper sources using `javac --release 25` and mapped `bank-demo/composer` into a new scoped Markdown vault at `outputs/bank-demo-c6-validation/vault`, workspace ID `bank-demo-c6`. Existing outputs and demo sources were preserved. Mapper succeeded in 8.52 seconds of process wall time (its internal summary reports seven seconds), with three channels, 10 operation views, 139 entity notes, 24 unused inventory notes, and 16 diagnostics.

Imported that exact generated vault into separate fresh INTERNET and IVR run databases, using the actual channel production source projects and installed JDK inventory, with no fabricated classpath or replacement decisions. INTERNET import took 0.42 seconds and preparation took 13.71 seconds for seven contexts. IVR import took 0.38 seconds and preparation took 4.89 seconds for three contexts. The Python process lifetime peak RSS was 71,434,240 bytes; both channels ran in that process, so this is not an independent per-channel peak or Mapper JVM memory measurement. Each imported inventory contains 139 definitions, 139 usages, 10 available operation contexts, and 324 context bindings.

All 10 selected contexts are blocked, with no native generation attempted. Evidence includes unresolved `ErrorBody`, ambiguous contexts (including `GetClientLinksCtxt`), absent/unverified format/decorator/framework implementations, absent declared visibility of shared XML Java sources from the selected channel projects, and unresolved `java.sql.*` review obligations. These are intake/preparation findings, not proof that every source definition is absent or that Composer itself rejects the demo. Resolve the specific manifest bindings, demo source-project visibility/replacement policy, and dependency findings before attempting real native acceptance; do not suppress the diagnostics or infer visibility from a unique candidate.

Reproduction and evidence are saved under `outputs/bank-demo-c6-validation`: `mapper.log`, `mapper-measurement.json`, `validate_demo.py`, `source-projects.json`, `converter.log`, `validation-summary.json`, and per-channel `profile.json`, `run.sqlite`, import measurement and preparation/acceptance reports. The validation script uses a fresh generated vault and fresh databases; use a new output directory for another independent run. This demo run establishes Mapper/import execution and exposes blockers; it does not complete C6 or establish enterprise performance.

## Expected files to change:

The following lists implementation targets across all milestones; C0 must confirm each before modification. Files initially marked **proposed** are now implemented for the first milestone where noted below. Existing unrelated local edits must be preserved.

First-milestone additions alongside the originally listed targets:

- [Scoped layout configuration](../../source/constants.py): one additive setting, retaining the legacy default.
- [Mapper generation safety](../../source/tools/workspace_intake_tools/mapper_generation.py): explicit scoped settings and safe output checks.
- [Schema-three inventory importer](../../source/tools/composer_mapper_tools/shared_vault_importer.py): atomic canonical/context import; schema-two path is retained.
- [Context persistence schema](../../source/tools/composer_mapper_tools/scoped_context_state.py): additive execution-context, binding, channel, and intake evidence tables.
- [Intake evidence snapshot](../../source/tools/composer_mapper_tools/scoped_intake_evidence.py): buffered hashes, channel/configuration evidence, and validation progress.
- [Qualified intake tests](../../source/tests/test_shared_vault_intake.py): selection, identity, rollback, paths, calls, and large inventory coverage.

The qualified access API and three proposed model files below are implemented. Remaining closure/conversion models are unchanged for this milestone. The [vault guide](../scoped_vaults.md) now distinguishes inventory support from conversion support.

### Intake, import, and qualified access

- [Workspace intake](../../source/workspace_intake.py)
- [Vault validator](../../source/tools/workspace_intake_tools/vault_validator.py)
- [Channel validator](../../source/tools/workspace_intake_tools/channel_validator.py)
- [Manifest reader](../../source/tools/composer_mapper_tools/vault_manifest.py)
- [Vault importer](../../source/tools/composer_mapper_tools/vault_importer.py)
- [Scoped importer and persistence](../../source/tools/composer_mapper_tools/scoped_vault_importer.py)
- [Channel-note parser](../../source/tools/composer_mapper_tools/channel_note_parser.py)
- [Scoped access API — proposed](../../source/tools/composer_mapper_tools/scoped_vault_access.py)
- [Qualified entity reference — proposed](../../source/models/scoped_entity_reference.py)
- [Execution context model — proposed](../../source/models/operation_execution_context.py)
- [Step occurrence model — proposed](../../source/models/scoped_step_occurrence.py)
- [Conversion models](../../source/models/conversion_models/conversion.py)
- [Conversion component](../../source/models/conversion_component.py)
- [Source identity model](../../source/models/source_component_identity.py)

### Closures and dependencies

- [Closure builder](../../source/tools/conversion_tools/closure_builder_tool.py)
- [Closure validator](../../source/tools/conversion_tools/closure_validator_tool.py)
- [Channel filter](../../source/tools/conversion_tools/channel_filter_tool.py)
- [Format resolver](../../source/tools/conversion_tools/format_dependency_resolver_tool.py)
- [Decorator resolver](../../source/tools/conversion_tools/decorator_chain_resolver_tool.py)
- [Serialization planner](../../source/tools/conversion_tools/serialization_plan_builder_tool.py)
- [Context hierarchy resolver](../../source/tools/conversion_tools/context_hierarchy_resolver_tool.py)
- [Context field resolver](../../source/tools/conversion_tools/context_field_resolver_tool.py)
- [Context hierarchy persistence](../../source/tools/state_store_tools/context_hierarchies.py)
- [Context field persistence](../../source/tools/state_store_tools/context_field_inventories.py)
- [Java implementation resolver](../../source/tools/conversion_tools/java_impl_resolver_tool.py)
- [Java source reader](../../source/tools/java_analysis_tools/java_source_reader.py)
- [Conversion component set](../../source/tools/conversion_tools/conversion_component_set.py)

### Contracts, generation, and runtime

- [Operation-call closure](../../source/tools/conversion_tools/operation_call_closure.py)
- [Call graph and contract persistence](../../source/tools/state_store_tools/operation_calls.py)
- [Behavior call integration](../../source/runtime/behavior_conversion/operation_calls.py)
- [Runtime checkpoints](../../source/runtime/checkpoints.py)
- [Behavior runner](../../source/runtime/behavior_conversion/runner.py)
- [Assembly runner](../../source/runtime/operation_assembly/runner.py)
- [Behavior unit builder](../../source/tools/conversion_tools/behavior_unit_builder.py)
- [Service-flow evidence instructions](../../source/agents/behavior_conversion/service_flow.py)
- [Route-test evidence instructions](../../source/agents/behavior_conversion/operation_route_tests.py)

### State, identity, reuse, and invalidation

- [State schema](../../source/tools/state_store_tools/schema.py)
- [Component identity](../../source/tools/component_inventory_tools/identity.py)
- [Inventory construction](../../source/tools/component_inventory_tools/inventory.py)
- [Inventory persistence](../../source/tools/state_store_tools/component_inventory.py)
- [Component registry](../../source/tools/artifact_registry_tools/component_registry.py)
- [Reuse resolver](../../source/tools/artifact_registry_tools/reuse_resolver.py)
- [Native Java artifact persistence](../../source/tools/state_store_tools/native_java_artifacts.py)
- [Invalidation](../../source/tools/state_store_tools/invalidation.py)

### Tests and documentation

- [Intake tests](../../source/tests/test_workspace_intake.py)
- [Scoped identity tests](../../source/tests/test_scoped_vault_identity.py)
- [Closure tests](../../source/tests/test_closure_builder.py)
- [Dependency tests](../../source/tests/test_dependency_resolvers.py)
- [Decorator tests](../../source/tests/test_decorator_chain_resolver.py)
- [Call and contract tests](../../source/tests/test_operation_calls.py)
- [Unit-builder tests](../../source/tests/test_behavior_unit_builder.py)
- [Scoped workflow tests](../../source/tests/test_operation_scoped_workflow.py)
- [Behavior pipeline tests](../../source/tests/runtime/test_behavior_pipeline.py)
- [Registry tests](../../source/tests/test_artifact_registry.py)
- [Invalidation integration tests](../../source/tests/e2e/test_invalidation_e2e.py)
- [Vault contract](../scoped_vaults.md)
- [Migration run instructions](../running_migrations.md)
- [Mapper migration design](composer_mapper_vault_hierarchy_migration_plan.md)
- [Composer manual](../comp-manual/wsbcc_developer_manual_v2.md)
- [This implementation plan](scoped_vault_converter_implementation_plan.md)

New fixtures and narrowly focused tests may be added beside these suites once C0 identifies their exact paths. Mapper/Excel implementation changes are outside scope unless a separately documented input-contract gap requires approval.

## Acceptance matrix

| Case | Required result |
| --- | --- |
| Completed schema-three vault without legacy registry | Intake succeeds using manifest evidence; CLI uses supported arguments. |
| Incomplete generation, corrupt hash, unsafe path, unsupported schema | No ready import or conversion; previous valid run remains usable. |
| Enterprise-size manifest | Incremental hashing/import, bounded intermediate allocations, visible progress and elapsed time. |
| XML operation consumed by SME, WEB, and another channel | One canonical operation note; independent execution contexts and selected overrides. |
| Local operation/resource override | Selected local definition wins; unrelated channels retain their own selection. |
| XML inventory with many uncalled operations | No inherited inventory explosion or fabricated executable roots. |
| Requested consuming context absent | Explicit missing-evidence blocker, not XML-default synthesis. |
| Equal resource IDs in different owners/parents | Independent qualified resolution and persistence. |
| Exact and case-variant repeated step labels | Distinct ordered occurrences, original spelling, separate parameters and call sites. |
| `onlyFor` excluded middle step | Canonical source position retained; effective order, entry, and routing use selected steps. |
| Named self/forward/wrapped/backward jumps, `next`, `end` | Targets match verified case-sensitive current-inclusive Composer behavior. |
| Same return code on different steps | Each occurrence retains its own return-body format binding. |
| Each of the twelve indexed wrappers | Repeated child names survive in order, including decorator association. |
| Keyed wrapper and root same-ID `fmtDef` | Last same-key definition wins in the correct scope; unnamed children remain. |
| Nested definitions and `refFmt`/`refFormat` | Parent identities remain distinct; references resolve without becoming replacement definitions. |
| Equal context names with different parents | Context-specific hierarchy/fields; existing cycle and ambiguity checks remain. |
| Duplicate FQCNs and unresolved classpath | No arbitrary class choice; conversion requires origin proof. |
| UTF-8, ASCII, Windows-1255 Java | Correct evidence decoding, unchanged byte hashes, size guard retained. |
| Literal `#`, literal `%23`, spaces, fragments, both link modes | Correct file resolution without double decoding or identity changes. |
| Repeated complex calls with different targets | Each occurrence binds its selected target context and contract. |
| Excluded called operation or call cycle | Existing dependency/contract policy applies; no silently missing call. |
| Shared XML change versus local override change | Actual qualified consumers invalidated conservatively; unrelated same-name records remain independent. |
| Shared implementation with different configuration | Analysis reuse allowed only with proof; configured output is not incorrectly shared. |
| Changed evidence on an existing checkpoint | Explicit refresh/replanning before reuse; no silent old-run migration. |
| Supported legacy/schema-two inputs | Existing supported behavior retained; unsupported scoped paths remain gated. |
| Scoped conversion through both runtime paths | Generated output reviewed, compiled, and behavior-tested with traceable context/occurrence evidence. |
| Shared reader changes | Relevant Mapper and both Excel-generator regressions remain green. |

## Delivery order and reporting

First-milestone validation (2026-10-25):

- `PYTHONPATH=source python -B -m pytest source/tests/test_shared_vault_intake.py source/tests/test_workspace_intake.py -q -p no:cacheprovider`: **25 passed**, including a 1,500-additional-definition inventory, rollback, changed channel evidence, context selection, schema-two compatibility, and CLI safety.
- `PYTHONPATH=source python -B -m pytest source/tests/test_scoped_vault_identity.py source/tests/test_composer_mapper_tools.py source/tests/test_operation_calls.py source/tests/test_mapper_channel_imports.py -q -x --tb=short -p no:cacheprovider`: **140 passed** (three third-party warnings).
- The added `test_qualified_import_preserves_real_mapper_consuming_contexts` check: **1 passed**, verifying actual generated XML inheritance, consuming-channel overrides, selected steps, and qualified calls.
- After the final access adjustment, the focused suites excluding the unchanged large-inventory case: **24 passed, 1 deselected**. Python syntax, plan links, and scoped whitespace checks passed.

These are inventory/access checks and existing regressions. They do not establish enterprise-scale memory bounds or end-to-end generated conversion readiness. No commit or push is part of this milestone implementation request.

C3 validation (2026-10-25):

- `PYTHONPATH=source python -B -m pytest source/tests/test_scoped_closure.py -q -x --tb=short -p no:cacheprovider`: **24 passed** before the final explicit malformed-reference check was added. Coverage includes real Mapper output, repeated steps, keyed/indexed nodes, nested definitions, context overrides/cycles, Java profile/revision checks, captured helpers, binary-origin checks, hash paths, and upstream blockers.
- `PYTHONPATH=source python -B -m pytest source/tests/test_closure_builder.py source/tests/test_dependency_resolvers.py source/tests/test_decorator_chain_resolver.py source/tests/test_context_hierarchy.py source/tests/test_context_field_resolver.py source/tests/test_java_source_dependencies.py source/tests/test_source_discovery.py source/tests/test_java_classpath.py -q -x --tb=short -p no:cacheprovider`: **53 passed**, with three third-party warnings.
- First-milestone intake/access regression excluding its unchanged large-inventory case: **24 passed, 1 deselected**.
- After compacting external behavior evidence through the existing shared helper, call-cycle, retention, and source-change checks: **4 passed, 20 deselected**. The final frozen-generation-flag and malformed-format-reference checks: **2 passed, 23 deselected**. Across the C3 and regression suites, **102 distinct tests passed**; repeated targeted runs are not counted twice.
- Python syntax/whitespace checks passed for all **20** C3 Python files, and plan links resolve. The JDK syntax scanner was exercised by the scoped and existing Java dependency tests, including Windows-1255 source bytes.

The next milestone is C4. Contracts, generation/assembly runners, conversion units, and public call behavior are still pending. No enterprise-scale conversion or end-to-end generated behavior is claimed by C3 inspection readiness.

Deliver C0–C2 first as an inspectable intake/access increment with conversion still gated. Follow with C3, then C4 and C5, and finally C6 enablement. Do not bypass missing closure, contract, Java-origin, or reuse evidence merely to run generation early.

For each increment report changed files and why, actual validation commands/results, remaining blockers, supported schema/profile combinations, and any measured performance limits. Preserve source XML, existing public behavior, unrelated local work, and legacy compatibility throughout. First-milestone fixtures demonstrate inventory/access behavior; enterprise-scale performance and generated-conversion correctness remain C6 acceptance work.


### C8 implementation record

Implemented opt-in `scoped_native_mode: behavior_units_v1` for the behavior-unit strategy. Both runtime entry points share the existing generation/review/compile/test engine through qualified execution adapters. Other strategies remain blocked; `prepare` remains the default.

Expected files to change:

- [Native integration package](../../source/runtime/scoped_native/runner.py), [payload adapter](../../source/runtime/scoped_native/payloads.py), [execution boundary](../../source/runtime/scoped_native/scope.py), [result proof](../../source/runtime/scoped_native/results.py), [plan approval](../../source/runtime/scoped_native/plan_approval.py), and [Maven coordinates](../../source/runtime/scoped_native/project_names.py): contextual routing, typed plans, separate plan approval, task scoping and native evidence.
- [Profile](../../source/models/pipeline_configuration.py), [policy fingerprint](../../source/tools/conversion_tools/scoped_reuse/fingerprints.py), [resume](../../source/runtime/checkpoints.py), [CLI discovery](../../source/cli/discovery.py), and [report routing](../../source/runtime/workflow_stages.py): explicit capability and persisted phases; default remains preparation-only.
- [Behavior runner](../../source/runtime/behavior_conversion/runner.py), [generation](../../source/runtime/behavior_conversion/generation.py), [service request](../../source/runtime/behavior_conversion/service_flow.py), [call freshness](../../source/runtime/behavior_conversion/operation_calls.py), [native ownership](../../source/runtime/behavior_conversion/ownership.py), [evidence collector](../../source/runtime/behavior_conversion/evidence.py), [assembly entry](../../source/runtime/operation_assembly/runner.py), [service packaging](../../source/runtime/service_generation/runner.py), and [approval reader](../../source/runtime/intake_plan.py): narrowly scoped qualified branches, retaining existing validation and legacy behavior.
- [Real native integration tests](../../source/tests/runtime/test_scoped_native.py), [boundary tests](../../source/tests/runtime/test_scoped_native_safety.py), this plan, and [vault guide](../scoped_vaults.md): capability acceptance, safe reuse and documented limits.

No Mapper, Excel, converter legacy algorithm, demo source, or deployment approval changes are part of C8. Qualified plans use additive state so they do not alter the existing intake-plan publish-before-caller policy. Fresh intake is required for the new policy fingerprint; retain prior state for rollback.

Validation uses deterministic model candidates and review responses, real offline Maven/JUnit, order-sensitive repeated occurrences and an original-fixture Java oracle. Gate 3 remains human/pending in the native fixtures. Packaging evidence collection is exercised; production deployment, real Composer equivalence, and complete bank-demo native acceptance are not claimed. C9 remains open.


C8 verification (2026-10-25): 13 native/boundary checks passed, including both real offline Maven/JUnit entry paths, unchanged-run model-free resume, and the original-fixture Java oracle (511.39 seconds). The separate final boundary run also passed all 10 checks. Existing workflow/assembly/scoped reuse suites passed 54 checks; startup/boundary/conversion suites passed 48; the final runtime-focused rerun passed 43. These suites overlap; the counts are not additive. Candidate/review fixtures are deterministic, not live model assessments. Existing human approval and final deployment evidence checks remain enforced. No changes have been committed or pushed for this milestone.


### C9 execution — 2026-10-25 (live bank-demo run in progress)

Fresh evidence is isolated under `outputs/bank-demo-c9-20261025`. `run_checks.py` compiles current Mapper sources with JDK 25 into a new runnable JAR, invokes normal converter startup on the bank demo, and resumes the new schema-three run. Existing demo source bytes and previous run directories are preserved. The initial human plan gate was reached normally; the user then explicitly approved the plan and authorized automatic policies for every gate for this C9 check. `continue_checks.py` persists those automatic policies only in this run's saved profile. This does not claim manual review and does not bypass compiler, test, model-review, evidence, or finalization checks.

Completed checks:

- 268 scoped/Mapper/Excel/converter regression checks passed (880.49 seconds).
- 13 native runtime/boundary checks passed through both entry paths with real offline Maven/JUnit (742.23 seconds); deterministic candidate/review fixtures are separate from live bank-demo conversion.
- 34 service generation, packaging/finalization, assembly and behavior regressions passed (72.73 seconds); those regression fixtures do not establish packaged bank-demo services.
- Fresh startup completed in 27.13 seconds, including Mapper generation and import. Preparation/plan resume took 62.34 seconds. The Mapper reported 3 channels, 10 operation contexts, 133 entity notes, 9 unused inventory notes, and no diagnostics. All 10 selected contexts prepared with 83 configured units and no preparation blockers.
- Startup/preparation Python process lifetime peak working set was 213,721,088 bytes. An independent repeat Mapper JVM run took 6.51 seconds with a sampled OS peak working set of 114,872,320 bytes. These processes ran alongside checks; timings are not isolated benchmarks or enterprise measurements. The continuation process peak is sampled separately into `converter-memory.json`.

The actual bank-demo run uses the configured live model and actual Maven validators. Initial invalid generated candidates were rejected and corrected; unit acceptance, operation assembly, service packaging and finalization remain independently recorded. `observe_checks.py` updates `live-status.json` and `acceptance-report.md` until the continuation process exits. End-to-end acceptance remains false unless the persisted run reaches completed `migration_approved` with all 10 operations accepted. The live process and its automatic report must be inspected before declaring C9 complete. No native capability is enabled by default, no missing runtime equivalence evidence is invented, and no production deployment is performed.

Only this plan and the scoped-vault guide are changed for C9 reporting; executable validation helpers, logs, profiles and measurements are isolated in the new output folder. No application-code defect has yet required a product change. Mapper, Excel, converter implementation, demo inputs, and unrelated local changes are preserved. Nothing has been committed or pushed.


### C9 correction - decorator source evidence (2026-10-26)

The stopped run reached 25/83 accepted units and 0/10 accepted operations. Its
`StandardErrorRSFmt` candidate failed a nil-attribute assertion after three attempts.
Inspection of the persisted model request confirmed that `NilDecorator.java` was
supplied. The demo source described unconditional nil behavior and shared generation
guidance reinforced it; this was not a missing decorator source in that request.

The demo now supplies an executable context/configuration-dependent attribute decorator,
its parent and configuration dependency. Derive generated behavior and test expectations
from verified mapped Java source, including transitive dependencies and runtime branches;
do not use tag names as fixed behavioral policies. Native output keeps explicit typed
inputs/collaborators rather than rebuilding Composer Context or a decorator interpreter.
Existing dependency-first unit planning and source-closure verification remain in place;
supporting classes may be translated together in their consumer's native bundle.

Regression checks execute the demo's conditional source behavior and prove a mapped
decorator, its superclass and transitive helper arrive intact in model request evidence.
A fresh mapping/preparation is required after changing demo source. The previous run and
its evidence remain untouched; no resume, end-to-end acceptance or deployment is claimed.


Verification: 40 qualified closure/workflow checks passed. A separate focused run passed
26 checks (including the executable demo Java oracle, request evidence and prompt/feedback
checks), with one broader existing dependency-runner assertion failing because it expects
two model requests while the current route-test flow produces three. Loading the previous
HEAD prompt contents in memory reproduced that same failure; the unrelated test is unchanged.
Fresh Mapper/import/preparation under `outputs/decorator-source-check-20261026` prepared all
10 contexts without blockers and confirmed the four relevant Java sources in the
`GetClientLinksOp` error-format unit. This is source-evidence/preparation validation, not
live generated-code or end-to-end acceptance. The failed C9 directory remains unchanged.
