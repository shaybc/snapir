# Converter support for scoped Composer Mapper vaults

Status: Proposed converter implementation plan. This document changes no application behavior.

## Objective

Enable the converter to consume the current scoped Mapper vault without flattening its folders or confusing equal names from different channels, operations, or source definitions. Keep original business names for generated behavior and diagnostics while carrying qualified source identities through conversion and persistence.

The Mapper layout, source-channel detection, readable filenames, short XML resource-origin paths, manifest reader, call discovery, and both Excel exporters are already implemented. This work concerns converter compatibility. The broader [vault migration plan](composer_mapper_vault_hierarchy_migration_plan.md) remains the design reference.

## Current implementation and concrete gaps

| Area | Current behavior | Required correction |
| --- | --- | --- |
| Intake validation | Requires the legacy channel-operation registry file | Validate a scoped manifest and its channel/operation inventory instead |
| Mapper invocation during intake | Passes `--out`, whereas the current Mapper requires `--vault` | Correct the existing argument and explicitly configure scoped generation when enabled |
| Scoped import | Stores canonical definitions and separate usages, but parses only frontmatter | Parse the note sections needed by conversion as well as identity metadata |
| Channel mappings | Legacy import reads top-level channel notes; scoped import does not populate equivalent mappings | Import effective scoped channel mappings and import provenance |
| Closure entry | Explicitly rejects scoped runs | Retain the gate until the consumers below are migrated and verified |
| Operation and step lookup | Several queries select by run, kind, and bare logical ID | Resolve an effective operation and its step usages explicitly |
| Same-ID channel variants | Scoped Mapper now selects steps by `onlyFor` and retains unused variants in inventory | Preserve each source occurrence; consume only the selected channel's operation usages, never a global ID winner |
| Repeated step labels within one effective flow | Composer resolves repeated labels by ordered positional lookup, including self/backward jumps | Preserve occurrence identities and order; do not reject duplicates or collapse routing by label |
| Resource lookup | Formats and contexts are selected by name; context hierarchy dictionaries are keyed by name | Resolve selected definitions within the consuming operation/channel |
| Java lookup | Some paths select/deduplicate by FQCN and resolve tags without channel | Carry the selected source implementation and effective channel mapping |
| Runtime orchestration | Checkpoint and behavior runners read legacy source tables before closure | Route both through the scoped operation reader |
| Behavior units | Reads legacy operation metadata, while configured inventory has separate definition/use IDs | Bridge the identity systems by verified source coordinates |
| Reuse and invalidation | Some registries and queries use logical names without source scope | Match canonical source identity, revision, and relevant conversion context |

The existing operations and channel-operation tables already include channel in their keys. Preserve those useful boundaries rather than replacing them indiscriminately.

## Input contract

Use the manifest to enumerate effective operations, entity views, and definition identities. Read note paths from manifest entries. Do not reconstruct paths using project names, old global folders, or XML selectors. The simplified resource folders require no converter-specific path parsing.

An operation is selected by channel plus operation name and resolved to its effective operation identity. An entity reference identifies its canonical definition and the applicable operation usage. Keep source IDs, FQCNs, and step names as labels and behavioral values; do not substitute opaque keys into generated XML contracts or flow expressions.

Separate these concepts in models and APIs:

- Canonical source definition and exact source coordinates.
- Effective operation under a consuming channel.
- A definition's usage by that operation.
- Source content revision and generated-note revision.
- Display name and original source ID.

Availability under a channel does not prove that an operation uses a resource. A class note or matching FQCN does not prove which Java implementation loads.

### Channel-specific step variants

One operation XML may contain multiple `opStep` elements with the same `id`, with or without `onlyFor` restrictions, and potentially different implementations, parameters, and transitions. These are separate source occurrences, identified by their exact XML selectors and canonical definition IDs. Equal step IDs or implementing classes do not authorize merging them or reporting a duplicate-ID conflict.

Capitalization variants such as `SetSITE` and `SetSite` belong to the same duplicate group for Mapper filename allocation. They remain distinct ordered source occurrences with original spelling and configuration; this grouping is not a canonical-definition merge. The converter must follow their manifest usages and explicit target paths rather than infer identity from case-folded names or occurrence folders. Runtime named-transition matching remains exact/case-sensitive. Mapper destination reservations prevent overwrites during generation, but a failed run still requires a fresh complete vault; the converter must reject its incomplete marker rather than salvage partial notes.

The current scoped Mapper already emits an effective operation view for each consuming channel. Import its ordered Steps references and their explicit definition/usage identities. Preserve `onlyFor` as evidence; match channel names without case sensitivity, support comma-separated names, and treat absent or blank restrictions as unrestricted. Imported operations use the consuming channel, not their source channel, for applicability.

Keep inventory-only variants available as source evidence, but do not add them back to an operation's executable steps by scanning inventory or matching bare IDs. Do not infer applicability from the readable inventory folders. Import ordered manifest `step_notes`, `entry_step_note`, zero-based `step_index`, and resolved `transition_targets` where present; cross-check against the note links and source selectors. Older scoped manifests lacking these additive fields require explicit reconstruction from ordered operation links and a verified lookup implementation, never a bare-name map.

Repeated IDs remain valid even when multiple occurrences are applicable in one effective operation. Resolve each named transition from its source occurrence's effective index: choose the first exact-label match at or after that index, including itself, then search from the beginning if no match remains. `next` advances one occurrence and `end` terminates. Preserve self-jumps and backward jumps; do not reject a loop merely because it moves backward. A missing name produces runtime lookup result `-1` and must remain explicit evidence rather than borrowing an excluded step. Keep all definitions in imported evidence. See the [manual's positional routing explanation](../comp-manual/wsbcc_developer_manual_v2.md#repeated-labels-and-positional-routing).

## Phase one intake and complete scoped import

1. Detect legacy versus scoped input before legacy folder/registry validation.
2. Validate scoped manifests with the existing shared reader. Preserve rejection of incomplete generation, modified notes, unsafe paths, unsupported versions, and conflicting identities.
3. Resolve target channels and selected operations from scoped inventory. Preserve include/exclude and existing channel-import behavior.
4. Fix the intake Mapper argument mismatch. Supply stable workspace identity and explicit scoped-layout selection without changing the default release behavior prematurely.
5. Parse operations, steps, formats, contexts, and Java notes using existing parsers. Preserve parameters, transitions, format roles/structures, context parents, and source metadata alongside the scoped identity envelope.
6. Import channel notes and effective tag mappings. Bind the channel-note contents and import provenance to the intake evidence snapshot; they must not change silently while an operation resumes. The current manifest lists channel names but does not list channel notes as hashed entity entries, so record that evidence explicitly during intake.
7. Surface resource diagnostics as well as call diagnostics. Associate blockers with affected selected operations. Do not let an unresolved context appear ready merely because call discovery has no issues.
8. Keep canonical definitions and operation usages separate. Do not populate a global bare-name compatibility table with arbitrary winners.

Gate: the latest vault imports complete conversion inputs, correct scoped mappings, definitions, usages, and actionable diagnostics. Legacy intake behavior still passes its tests.

## Phase two shared operation and resource access

Introduce a small typed access layer over scoped inventory. Its public responsibilities should include selecting an effective operation, reading its parsed note, resolving an explicit reference, enumerating its steps/resources, and reporting missing or ambiguous resolution.

Inputs carry run identity and effective operation context explicitly. Do not use hidden global context, mutate database views per operation, or guess a channel from whichever same-name row appears first.

Resolve operation-view references directly to their manifest entries. For resources available only in channel inventory, use the recorded source evidence and verified Composer precedence. Preserve ambiguities when a reference is not resolved. Do not merge duplicate context declarations simply because names, attributes, or bytes match.

Maintain legacy adapters only where they preserve existing behavior and an unqualified identity is unambiguous. Callers must know whether they are reading a legacy artifact or a scoped definition usage.

Gate: same-name operations and steps can be retrieved independently; resource ambiguity is explicit; readers are independent of resource folder depth.

## Phase three scoped dependency closure

Update closure to retrieve the selected operation's ordered step usages, validate their `onlyFor` applicability, and build routing from those usages. The scoped Mapper has already selected the effective channel view; validation must not reconstruct its steps from global inventory or discard occurrence identity. Retain original transition labels as business values alongside the resolved target occurrence. Routing models and generated code must use occurrence positions/identities rather than a dictionary keyed only by step ID. Preserve existing legacy filtering through its adapter.

Resolve request, reply, and error formats using qualified references. Traverse nested formats by definition identity, not name alone. Preserve serialization rules, decorators, mapped tags, database lookup requirements, and existing validation.

Consume the Mapper's effective format collection view according to the [manual's confirmed twelve-wrapper list](../comp-manual/wsbcc_developer_manual_v2.md#format-collection-policy): listed indexed wrappers retain repeated children in order; all other wrappers default to keyed collections with last-same-key replacement within that sibling scope. Do not re-add overridden declarations from raw source, compare their contents to select a winner, collapse indexed children, or treat `refFmt` as a definition. Retain original selectors and identities of surviving occurrences, including ordinal gaps after replacement. Different parents and different source files do not become one registry merely because names match. Changing the selected last declaration or wrapper policy must invalidate affected conversion reuse. Converter implementation remains gated and is not part of this Mapper change.

Build context inheritance and accessible fields from qualified context definitions. Persist scoped hierarchy and field results without collisions between same-name contexts. The current bank demo contains duplicate context declarations in defaults and operation files; keep their existing unresolved diagnostics until source precedence is established. Compatibility work must not silently choose one to make tests ready.

Resolve Java references against the effective source/classpath environment. Use originating project/source roots, dependency entries, mapping provenance, selected source or binary origin, and revision evidence. Preserve unresolved status when origin cannot be established. Reuse existing source inventory and dependency analysis; do not introduce a separate name-only resolver.

Carry definition/use identities alongside original names in closure models, Java references, format sets, source components, and routing evidence. Include the selected definitions and relevant resolution environment in freshness fingerprints. Preserve operation-call dependencies and published API boundaries.

Gate: closure selects exact expected sources, preserves routing behavior, and blocks only actual missing/ambiguous prerequisites. A dependency-free call graph does not override unresolved format/context/Java evidence.

## Phase four identity bridge and runtime consumers

Mapper definition IDs and the Python component inventory's IDs are generated differently. Do not compare those hash strings directly or regenerate existing implementation IDs from note paths. Bridge by stable workspace identity, normalized source-relative file, exact definition selector, and verified revision. Check selector conventions explicitly before accepting a match.

The Python inventory currently defaults workspace identity to an absolute workspace URI unless supplied. Use the manifest's stable workspace identity where compatible, and preserve existing explicit identities through a recorded mapping. Moving a checkout must not silently establish a different source implementation.

Update checkpoint and behavior runners before they prepare contexts or call closure. They currently query legacy operation rows directly. Update behavior-unit construction, task packets, checked component sets, and assembly inputs so operation scope and selected definitions survive every stage.

Preserve original operation/step names in generated control flow. Internal conversion units, tasks, review records, and output ownership must distinguish unrelated same-name inputs. Genuine shared implementations may still serve multiple operation usages under the existing reuse policy.

For repeated step IDs within one source operation, bridge each occurrence using its exact source selector and definition ID. Carry the selected usage into task packets, behavior units, and assembly; do not key configured step behavior by operation name plus step ID alone. Sharing a Java implementation does not imply sharing step configuration or routing.

Gate: both supported converter execution paths consume the same scoped selections; no legacy SQL lookup bypasses the access layer for a scoped run.

## Phase five persistence reuse and freshness

Audit source artifacts, configured definitions/uses, native artifacts, component registry, context hierarchies/fields, task keys, review evidence, and invalidation queries. Use additive schema changes or separate versioned tables where legacy primary keys cannot represent scoped identities. Keep source IDs available for display and backward compatibility.

Reuse requires the same originating definition, compatible revision, validated output, and relevant effective mappings/dependencies. Same names, copied notes, equal source bytes, or channel availability alone are insufficient.

A changed shared definition invalidates all dependent usages. A change to one channel-local context must not invalidate an unrelated namesake in another channel. Changes in selected dependency origin or mapping invalidate affected results even when the class source itself is unchanged.

Include step applicability, selected variant identities, and ordered routing evidence in freshness checks. A change to `onlyFor` can change a channel's executable flow without changing an implementation class. Re-evaluate the affected channel selections before reusing output. Retain the conservative source-file revision and whole-snapshot/new-run policies: do not claim variant-level invalidation precision where those existing evidence boundaries require broader invalidation.

Preserve the current initial policy: a different scoped evidence snapshot requires a fresh run; legacy and scoped identity models cannot silently replace each other in one run. Record schema and identity versions and required evidence fingerprints in persisted plans/checkpoints. Any cross-version resume migration is separate work requiring proven mappings.

Gate: no cross-definition reuse, exact dependent invalidation, and explicit compatibility failures for stale evidence or unsupported resume state.

## Phase six acceptance and gate removal

Keep the current scoped-conversion gate throughout incomplete stages. Replace it only when the selected execution path's intake, closure, units, reuse, review, invalidation, and resume boundaries are verified. Other unsupported modes remain explicitly blocked.

Run fresh scoped conversion on representative collision-free and duplicate-name fixtures. Test actual compiled output and routing evidence, not just import success. Bank-demo ambiguous resources may remain blocked with correct diagnostics; do not claim all operations convert until those source ambiguities are resolved separately.

Preserve legacy conversion and both Excel export paths. The standalone utility remains independent of converter installation. A converter identity change is not authorization to change public service endpoints, format contracts, error handling, logs, review gates, or source project layout.

## Expected files to change:

Only this planning document changes now. These are expected future implementation areas; each phase must declare its exact files before edits. Proposed modules are labeled. Audit additional call sites before changing them rather than refactoring adjacent code.

- [workspace_intake.py](../../source/workspace_intake.py), [vault_validator.py](../../source/tools/workspace_intake_tools/vault_validator.py), and [channel_validator.py](../../source/tools/workspace_intake_tools/channel_validator.py): scoped intake and current Mapper CLI contract.
- [vault_manifest.py](../../source/tools/composer_mapper_tools/vault_manifest.py), [scoped_vault_importer.py](../../source/tools/composer_mapper_tools/scoped_vault_importer.py), and [vault_importer.py](../../source/tools/composer_mapper_tools/vault_importer.py): complete scoped import, identity checks, and mapping evidence.
- [channel_note_parser.py](../../source/tools/composer_mapper_tools/channel_note_parser.py) and [composer.py](../../source/models/composer_models/composer.py): channel evidence and parsed scoped metadata where needed. Reuse existing entity parsers.
- Proposed [scoped_vault_access.py](../../source/tools/composer_mapper_tools/scoped_vault_access.py): explicit operation/resource lookup API.
- Proposed [scoped_entity_reference.py](../../source/models/scoped_entity_reference.py): typed definition/usage reference, preserving original names.
- [closure_builder_tool.py](../../source/tools/conversion_tools/closure_builder_tool.py), [closure_validator_tool.py](../../source/tools/conversion_tools/closure_validator_tool.py), and [channel_filter_tool.py](../../source/tools/conversion_tools/channel_filter_tool.py): selected-operation closure and local step membership.
- [format_dependency_resolver_tool.py](../../source/tools/conversion_tools/format_dependency_resolver_tool.py), [context_hierarchy_resolver_tool.py](../../source/tools/conversion_tools/context_hierarchy_resolver_tool.py), [context_field_resolver_tool.py](../../source/tools/conversion_tools/context_field_resolver_tool.py), and [java_impl_resolver_tool.py](../../source/tools/conversion_tools/java_impl_resolver_tool.py): scoped resource and implementation resolution.
- [conversion.py](../../source/models/conversion_models/conversion.py), [conversion_component.py](../../source/models/conversion_component.py), and [source_component_identity.py](../../source/models/source_component_identity.py): carry identity with existing business fields where necessary.
- [identity.py](../../source/tools/component_inventory_tools/identity.py), [inventory.py](../../source/tools/component_inventory_tools/inventory.py), and [component_inventory.py](../../source/tools/state_store_tools/component_inventory.py): bridge canonical source coordinates and existing implementation/configuration identities.
- [behavior_unit_builder.py](../../source/tools/conversion_tools/behavior_unit_builder.py), [conversion_component_set.py](../../source/tools/conversion_tools/conversion_component_set.py), and [operation_call_closure.py](../../source/tools/conversion_tools/operation_call_closure.py): selected evidence, component units, and call contracts.
- [checkpoints.py](../../source/runtime/checkpoints.py), [behavior runner](../../source/runtime/behavior_conversion/runner.py), and [assembly runner](../../source/runtime/operation_assembly/runner.py): replace pre-closure legacy lookups and preserve scope in scheduling/assembly.
- [schema.py](../../source/tools/state_store_tools/schema.py), [context_hierarchies.py](../../source/tools/state_store_tools/context_hierarchies.py), and [context_field_inventories.py](../../source/tools/state_store_tools/context_field_inventories.py): scoped result persistence and version handling.
- [component_registry.py](../../source/tools/artifact_registry_tools/component_registry.py), [reuse_resolver.py](../../source/tools/artifact_registry_tools/reuse_resolver.py), [native_java_artifacts.py](../../source/tools/state_store_tools/native_java_artifacts.py), and [invalidation.py](../../source/tools/state_store_tools/invalidation.py): identity-aware reuse, evidence, and freshness.
- [test_workspace_intake.py](../../source/tests/test_workspace_intake.py), [test_scoped_vault_identity.py](../../source/tests/test_scoped_vault_identity.py), [test_closure_builder.py](../../source/tests/test_closure_builder.py), and [test_dependency_resolvers.py](../../source/tests/test_dependency_resolvers.py): intake, parsing, scoped selection, and blockers.
- [test_behavior_unit_builder.py](../../source/tests/test_behavior_unit_builder.py), [test_artifact_registry.py](../../source/tests/test_artifact_registry.py), [test_behavior_pipeline.py](../../source/tests/runtime/test_behavior_pipeline.py), and [test_invalidation_e2e.py](../../source/tests/e2e/test_invalidation_e2e.py): runtime, reuse, and freshness acceptance.
- [Scoped vault guide](../scoped_vaults.md), [running_migrations.md](../running_migrations.md), and this plan: supported-mode and deployment instructions when each phase is completed.

## Validation and acceptance cases

| Case | Evidence required |
| --- | --- |
| New manifest with no legacy registry file | Intake succeeds using the scoped contract |
| Intake invokes Mapper | Correct vault argument, workspace identity, and explicit selected layout |
| Parsed scoped step | Original parameters, transitions, restrictions, and owner preserved |
| Channel note mappings | Effective mappings imported and bound to intake evidence |
| Same operation name across channels | Correct operation selected in both runners and closure |
| Same step name across operations | Correct implementation/parameters and local routing per operation |
| Same step ID with disjoint `onlyFor` conditions | Separate definitions retained; each consuming channel selects its own implementation, parameters, transitions, and call target |
| Lowercase or comma-separated `onlyFor`; blank/absent restriction | Case-insensitive selection, multiple allowed channels, and unrestricted common steps |
| Imported operation with channel variants | Selection uses consuming channel; source channel does not override applicability |
| Inventory-only excluded variants | Evidence preserved without adding excluded steps to executable closure |
| Repeated IDs with no restrictions, overlapping restrictions, or unrestricted plus matching restricted occurrence | Every applicable occurrence survives in source order with distinct identity, note, implementation, and configuration |
| Routing after channel selection | Exact entry occurrence, next/end behavior, inclusive named search, wraparound, self-jumps, backward jumps, and case-sensitive labels; excluded targets cannot resolve through inventory |
| Repeated CCComplexOpStep labels with different targets | All call sites and target operations survive; routing selects the correct source occurrence |
| Capitalization variants with the same implementation | Duplicate grouping allocates separate paths; original spelling, source selectors, configuration, order, and exact-case transition targets survive import |
| Changed `onlyFor` with unchanged Java class | Changed selection detected; stale closure, units, and assembled output cannot be reused |
| Same resource name across channels or sources | Selected definition retained; no arbitrary global winner |
| Defaults and operation-file context declarations | Proven selection or explicit ambiguity; not automatic merging |
| Context parent and fields | Correct qualified chain with existing cycle validation |
| Short inventory paths | Manifest enumeration works without reconstructing old folders |
| Shared source used by multiple operations | Separate usages; one proven implementation eligible for compatible reuse |
| Equal FQCNs from different origins | Correct source/classpath evidence or actionable unresolved status |
| Mapper IDs versus configured inventory IDs | Verified coordinate-based mapping; no hash-equality assumption |
| Source relocation | Stable workspace identity and explicit source-root resolution |
| Changed mapping, source, or selected dependency | Only affected consumers invalidated, including shared dependents |
| Different evidence in a saved run | Explicit refresh/new-run requirement, no stale reuse |
| Legacy input | Existing supported conversion behavior unchanged |
| Both Excel exporters | Existing values, waves, and diagnostics retained |
| End-to-end scoped operation | Correct compiled artifacts, routing, contracts, and review evidence |

Use generated temporary fixtures and fresh run databases. Preserve existing outputs, work, configs, and unrelated local changes. Do not depend on ignored local folders for committed regression tests; construct fixtures in tests or use existing tracked fixture sources.

## Recommended first implementation increment

Implement scoped intake validation, complete entity parsing, channel-mapping evidence, and the explicit operation/resource access API. Validate duplicate-name retrieval and unresolved context diagnostics before changing conversion behavior. Keep the conversion gate in place for this increment.

The next increment moves closure and both runtime callers onto that API, followed by units, reuse, and invalidation. Enable scoped conversion only after the complete supported execution path passes acceptance. No changes to the Mapper folder hierarchy are needed for these increments.
