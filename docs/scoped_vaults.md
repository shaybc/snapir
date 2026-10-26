# Scoped Composer Mapper vaults

Scoped output is an opt-in implementation of the vault hierarchy migration. It preserves source definition occurrences and writes canonical source notes with versioned consuming-channel connections. The legacy layout remains the default.

## Current compatibility

| Consumer | Scoped support |
| --- | --- |
| Composer Mapper | Opt-in generation into an empty destination |
| Excel Generator and repository operation exporter | Manifest validation, operation discovery, calls and migration waves |
| Vault inventory import | Schema two plus canonical schema-three notes, execution contexts, and qualified bindings; atomic inventory publication |
| Qualified closure inspection | Schema-three source/route/resource/context evidence, profile-based Java origins, and reachable dependency blockers; generation disabled |
| Native behavior-unit generation | C8 explicit opt-in; qualified generation, review, real compiler/test validation and resume; existing human gates retained |
| Full conversion rollout | C9 bank-demo acceptance and controlled enablement remain open |

This is not yet a completed end-to-end converter migration. Do not flatten scoped notes or remove the conversion gate. Legacy generation retains its existing behavior, but now reports colliding source occurrences on standard error and in `analysis/entity-collisions.md`. It cannot preserve those occurrences separately; use scoped generation to retain them.

## Generate a scoped vault

Build using the project-required JDK 25 or a compatible newer JDK:

```powershell
mvn -q -f source/composer-mapper/pom.xml package
```

Then run the packaged Mapper with your actual source and destination paths:

```powershell
java -jar source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\Composer\Workspace" --vault "C:\Mapper\scoped-output" --vault-layout scoped --workspace-id "enterprise-composer" --md true
```

The destination must be empty and outside the source tree. Use the same workspace ID when moving the same source workspace to another machine; use different IDs for independent source workspaces. An optional `--channel INTERNET` selects that channel's effective definitions, its implicit XML base, and declared imports.

Schema-three output writes each source definition once. Declared operations live at `channels/<definition-channel>/operations/<operation>/operation.md`; their canonical step notes include all source occurrences. Shared formats, contexts and Java candidates live in their source channel's resource inventory, using the existing resource-origin layout. Inline operation-owned resources use `resources/owners/<operation>/...` to keep same-label definitions in different operations separate. Nested format folders and original source selectors remain unchanged.

For example, SME's call to XML-defined `POB1Op` points to `channels/XML/operations/POB1Op/operation.md`. No `channels/SME/operations/POB1Op` copy is generated. The `operation_contexts` array records SME's selected step notes, entry step, transition targets, resource references, Java candidate evidence and operation calls. Canonical note annotations describe source/default evidence; these context records are authoritative for channel-specific resolution. XML availability does not enumerate XML's entire operation inventory again for each channel.

Unselected, shadowed, ambiguous and unused occurrences remain source inventory, subject to the existing keyed-format replacement policy. One canonical resource note can have multiple qualified consumers. Definition identities and source bytes are unchanged; manifest schema version is now 3 (identity version 1). Existing schema-two vaults remain readable by Excel. Converter inventory intake explicitly accepts schema three and persists its execution contexts separately from canonical notes. Full conversion remains gated rather than treating shared dependencies as isolated operation views.

For indexed nesting, the canonical notes retain the parent/ordinal layout:

```text
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt.md
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt/nested/1/GAC4HostSeSwitchCaseFmt.md
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt/nested/2/GAC4HostSeSwitchCaseFmt.md
```

Each surviving named format directly owned by a parent gets its original one-based ordinal across intervening XML wrappers. Formats nested inside that child start a new parent scope and extend the same layout recursively. The two same-ID blocks above both survive when their enclosing wrapper is indexed, for example `CCIColl`; a keyed wrapper such as `PSIONewXMLFormat` retains only the last same-key block. Original IDs, switch criteria, retained child order, and `refFmt` values remain intact.

Scoped format selection uses the wrapper policy documented in the [Composer manual](comp-manual/wsbcc_developer_manual_v2.md#format-collection-policy). The twelve confirmed indexed wrappers preserve all children in order. Every other wrapper is keyed: for a repeated explicit key (`id`, otherwise `dataName`, otherwise `name`), only the last direct child survives. Unnamed children are retained; tag name alone is not a collection key. References are pointers, not new definitions, and are not deduplicated by `refid`. Attached decorators remain with their selected formatter. Earlier declarations, their structure, and their nested inventory are omitted without comparing content. This policy applies within an XML sibling scope, including top-level `fmtDef` registry entries; it does not invent cross-file load order. The surviving definition retains its original source selector and identity. Source XML is never modified.

Nested inventory manifest entries include `parent_definition_id`, `parent_source_selector`, and the one-based `nested_format_index`. Definition identity remains the existing digest of workspace, kind, source-relative file, and exact XML selector; Markdown path allocation does not change that identity. Consumers follow the canonical definition ID and recorded note path rather than assuming operation-local copies. Existing reference-resolution rules are unchanged; this layout does not introduce a new global winner for an ambiguous ID. Legacy output is unchanged. Regenerate into a fresh vault to adopt the layout.

The completed manifest identifies source file and XML occurrence independently of content revisions. Each emitted definition has one canonical note; reachable runtime contexts refer to that note without duplicating it. Do not edit generated notes without regenerating the manifest: consumers reject notes whose hashes no longer match. Interrupted generation retains an incomplete marker and cannot be consumed as a complete vault. Generate a new vault to retry; this mode does not delete previous output.

## Hash characters and link destinations

Operation IDs, step labels, filenames and manifest paths retain literal `#` and `%` characters. Only Markdown link destinations are URL encoded: `#` becomes `%23`, and a literal `%23` in a filename becomes `%2523`. For example, the physical operation path `channels/XML/operations/#GPKOp/operation.md` is linked as `[#GPKOp](channels/XML/operations/%23GPKOp/operation.md)`. Encoding does not change definition identity or source XML.

In Obsidian mode, paths containing `#` or `%` use standard Markdown links with encoded destinations; ordinary paths keep wiki links. This follows [Obsidian's supported Markdown-link format](https://obsidian.md/help/links), avoiding ambiguous raw hashes in wiki targets. It does not rename files to work around viewer-specific filename restrictions.

Both Excel readers keep URI escapes until resolution, try the full filename first for older unescaped hash links, and remove a real heading fragment before decoding the remaining path exactly once. Percent signs in existing wiki filenames remain literal. Schema-three manifest references are filesystem paths and are never URL decoded. Vault-boundary checks remain in force.

Regenerate a fresh vault to update existing Markdown links, then use the updated standalone or built-in Excel generator. Existing source files, IDs and manifest coordinates do not need renaming. Old unescaped links are accepted when the exact file exists; regeneration avoids ambiguity between a hash filename and a heading fragment.

## Channel ownership

Channel discovery reads the declaration at `<project>/src/Xml Definition/Channel/<name>/dse.ini`. The channel directory supplies the name; the project name is not used to guess it. Java files beneath that same `src` folder receive the declared channel even when they are outside the XML definition tree. Files already inside a channel directory retain their direct channel assignment. Source-folder ownership is established before selected-channel and declared-import filtering.

Every non-XML channel automatically inherits XML as its lowest-precedence base, even without an XML import in its local `dse.ini`. XML is loaded once, declared imports retain their order, and the consuming channel is applied last. Local operation, format, context, formatter and decorator definitions override their XML counterparts. Include the XML channel's configuration and sources in the mapping root; a missing XML base is an error, not a complete partial inventory. Source ownership and Java classpath evidence remain separate from inherited availability.

An XML operation is traversed in another channel only when a declared operation calls it, directly or transitively. Each `(consuming channel, operation name)` context is resolved once, so cycles terminate. `onlyFor`, positional routing, formats, contexts and formatter/decorator mappings use the consuming channel's environment. Local operation overrides select another canonical source note; resource overrides change the context's references without changing XML's source note. XML has no implicit self-parent; real explicit import cycles remain errors.

## Java class origin

Java references retain candidate origins and `unresolved_classpath` status. A unique source candidate can be rendered as evidence, but is not asserted to be the implementation loaded by the operation. Equal FQCNs, bytes, or note copies do not establish sharing. Multiple candidates remain separate inventory definitions. Classpath selection and generated-code reuse require additional converter resolution evidence.

## Generate Excel

The standalone file still requires only Python 3.10 or newer and openpyxl:

```powershell
python -m pip install openpyxl
python "Excel Generator.py" "C:\Mapper\scoped-output" --output "C:\Reports\migration.xlsx" --include-relationships
```

Copy the entire generated vault, including its manifest, alongside access to the standalone utility. Excel does not require the original Composer source files. Calls and waves describe resolved operation-call relationships; they do not certify that format dependencies or Java classpaths are ready for conversion.

Both Excel generators use schema-three resolved connections instead of requiring a copied caller-channel operation file. They retain reachable consuming-channel identities in the dependency graph because overrides can change a called operation's dependencies; multiple graph contexts can link to one source note. Uncalled inherited operations do not become extra graph rows. Counts, dependency-wave calculations, workbook columns and commands remain unchanged. Legacy/schema-two discovery retains its existing behavior.

Regenerate into a fresh vault and use the updated Excel utility to adopt this layout. A completed older vault is not rewritten. Source note counts no longer grow by the whole XML inventory for every added channel; additional contextual connections can still require resolution work when actually referenced.

## Import and resumption

For existing schema-two vaults, scoped import stores canonical occurrences in `scoped_source_definitions` and views in `scoped_entity_usages`. It does not project them into the legacy bare-name source artifact table. Existing converter closure creation rejects scoped runs explicitly rather than selecting arbitrary namesakes. Saved operation contracts read format evidence from the selected operation view.

Schema-three import additionally stores `scoped_operation_contexts`, `scoped_context_bindings`, `scoped_channel_evidence`, and `scoped_intake_evidence`. Complete Markdown and parsed note evidence are retained without a second in-memory list of parsed notes. Manifest hashing uses buffered reads; a transaction publishes inventory readiness only after all records and channel/configuration snapshots are validated. Interrupted or invalid imports roll back. The qualified access API requires a run and an exact consuming context, preserves source/effective step positions, and never synthesizes a missing context from XML defaults. Contextual contract/workflow preparation is implemented; native conversion remains gated.

For workspace intake that generates a new scoped vault, configure `COMPOSER_MAPPER_VAULT_LAYOUT=scoped` and a stable `SOURCE_WORKSPACE_ID`. The legacy layout remains the default. The launcher uses `--vault`, requires an empty destination separate from the source tree, and validates the generated manifest before persisting the run. To intake an existing completed vault without regenerating it, set `COMPOSER_MAPPER_JAR=`. Configuration and Java-origin snapshots are evidence, not proof of the loaded classpath; later conversion stages must verify source revisions and origins.

Do not replace a legacy run with scoped input. Reimporting identical scoped evidence is allowed; changed evidence requires a fresh run. Preserve original vault/database pairs for existing legacy resume. Source overwrites in old vaults can only be recovered by regeneration from the original source.

## Qualified closure inspection

`tools.conversion_tools.closure_builder_tool.build_scoped_operation_closure(conn, operation_id, channel, run_id, composer_root, java_project=..., classpath_index=..., profile=...)` inspects an imported schema-three execution context. `java_project` identifies an explicitly selected production project in source discovery; `classpath_index` must describe its resolved analysis classpath. `profile` retains the existing external replacement/retention policy. Missing or ambiguous origins remain blockers, even when Mapper found only one source candidate.

The result preserves ordered step occurrences, per-occurrence routes and return-body formats, selected format roles, effective format trees, context ancestry/fields, Java origins, and calls. Original source bytes must match intake hashes. Named routes are checked against source order and channel selection. Indexed repeats retain independent selectors/decorators; keyed children use last-wins. Definition tags remain separate from format-body collection wrappers.

Only referenced definitions and reachable called contexts are analyzed. Blocked dependencies propagate to callers, while unrelated inventory does not become a conversion root or a global semantic blocker. Source/Java revisions are checked again before publishing the analysis. Field extraction remains static evidence; it does not establish exhaustive runtime access or behavioral equivalence.

Analysis is stored in additive `scoped_operation_closures` and `scoped_context_hierarchies` tables keyed by run and execution identity. `evidence_ready` is an inspection status with `conversion_enabled=false`. Qualified reuse/invalidation is implemented; native generation remains preparation-only by default and requires the explicit C8 capability below. No legacy closure or context table is reinterpreted.

## Contextual workflow preparation

Normal converter startup accepts `mapper_vault_layout: scoped` with an explicit nonblank `source_workspace_id` in the YAML profile. Existing profiles default to `legacy`. The saved `state/profile.json` retains the layout and identity. Scoped startup maps all available channels for the behavior-unit strategy, imports the selected consuming contexts, and pauses at `scoped_inventory_ready` before legacy context/planning readers. This checkpoint appears in the CLI Resume menu. Resume enters qualified preparation. By default it stops before native generation; the explicit C8 capability below can continue. `mapper_vault_layout` enables scoped intake; it does not enable native scoped conversion.

The corrected implementation plan separates C6 startup, C7 demonstrated preparation blockers, C8 native generation integration, and C9 end-to-end acceptance. Earlier references below to C6 acceptance use the original numbering; they do not imply that preparation alone proves native generation readiness.

Set the persisted converter profile's `scoped_java_project` to the explicit production source project (`.` for a conventional single-project workspace). Preparation uses the configured classpath and external replacement/retention policy. It does not infer production origin from a unique Mapper candidate.

For a multi-project workspace, `scoped_java_projects` maps exact consuming-channel names to production projects, for example `{INTERNET: WSBCC_INTERNET, IVR: WSBCC_IVR, XML: WSBCC_XML}`. An exact channel entry overrides `scoped_java_project`; other channels retain that fallback. Transitive project visibility must be declared in source metadata. Resolution may use an exact intake-captured source coordinate after proving that profile's visibility and uniqueness; a global or unique Mapper candidate alone still proves neither. Project selections and metadata participate in qualified freshness proofs.

C7 permits an indexed JDK package wildcard to proceed to the existing full syntax dependency check. It still rejects missing packages, competing source/library origins and unresolved actual type uses. Legacy wildcard classification is unchanged. A verified `CCComplexOpStep` dispatcher selected by operation-call evidence is not treated as an external service resource; its source remains in the unit evidence, and actual external lookups still require service resolution.

The C7 policy revision requires fresh intake/replanning for older checkpoints. Use the bank-demo scoped validation profile and fresh outputs. All demo contexts can pass preparation with captured implementations and existing embedded framework replacement contracts; this does not establish native generation readiness.

Resuming a schema-three run now prepares contextual HTTP contracts and independent configured step/format units before any legacy name lookups or model calls. Contracts use selected effective format trees and their transitive references; local overrides apply in every consuming channel. Existing escaped endpoint names and contract readiness rules are retained. Repeated step labels bind by occurrence, including calls to different targets and different response-body switches. Raw XML is retained as provenance alongside authoritative effective configuration.

Only imported selected operations (or an explicitly supplied subset) are prepared. Omitted callees require a pinned published XML API or produce a blocker. Competing application pins require explicit resolution. Intake-plan runs retain their publish-before-caller policy. Operation-call cycles require coordinated contracts; backward/self step routes do not create call cycles. Existing service-connection ownership and decision logic is retained within verified source boundaries.

The checkpoint, behavior runner, and assembly runner write `reports/3_dependency_closure_and_component_conversion/scoped_workflow_preparation.json` and persist additive `scoped_workflow_preparations` state. The report contains contextual contracts, occurrence bindings, and behavior/assembly/route-test inputs or explicit blockers. `prepared` means inputs are assembled; the run still stops at `conversion_scoped_gated` with `conversion_enabled=false`. C5 qualified reuse/invalidation is implemented; native execution requires the explicit C8 capability and its existing approval gates below. Legacy paths, Mapper output, and Excel behavior are unchanged.

## Qualified reuse and stale checkpoints

C5 intake captures source registry/layout evidence before preparation. Qualified checkpoints additionally track selected bindings, notes, source and archive revisions, source/classpath structure, contextual contracts and API pins, selection settings, and versioned conversion/testing policies. Unchanged prepared contexts can reuse their checked workflow inputs without rebuilding closures. `reused_contexts` identifies those contexts in the preparation report. Source excerpts may be shared by verified definition/revision; configured units remain separate across consuming contexts and configurations.

Changed inputs invalidate their saved consumers and non-published callers. Local overrides affect their selected consumers, shared definitions affect shared consumers, and physical-file hashes can conservatively invalidate several definitions from the same file. Registry/import changes follow the consuming channel's import chain. Project/classpath structure and connection decisions are conservative where finer provenance is unavailable. Pinned published APIs remain independent of callee source implementation changes unless the caller also directly consumes the changed source file.

The runtime stops at `conversion_scoped_stale`, lists affected contexts, and preserves artifacts and generated files. Restoring old bytes does not clear stale status automatically. Existing scoped runs without C5 intake/checkpoint proof require a new run. For changed source, regenerate into a fresh vault and perform fresh intake/replanning; retain the old vault/database/output together. A policy-only change can use a still-current vault in a new run, subject to the existing origin checks. Do not reset stale flags or overwrite an old run's evidence to force reuse.

The additive `scoped_checkpoints`, `scoped_reuse_entries`, `scoped_reuse_consumers`, and `scoped_stale_evidence` tables do not reinterpret legacy state. Scoped output reuse requires an exact context/unit identity, matching fingerprint, intact metadata and file hashes, and a successful validator. Output files must stay inside the run output root. C5 tests use deterministic output/validator fixtures; real native generation and its acceptance gates remain C6 work.

See the [migration plan](plans/composer_mapper_vault_hierarchy_migration_plan.md) for remaining converter stages and rollout gates.

## C6 acceptance measurements (partial)

Scoped runtime preparation also writes `reports/3_dependency_closure_and_component_conversion/scoped_acceptance.json`. It records UTC completion time, preparation elapsed seconds, process lifetime peak resident memory in bytes (or an explicit unavailable result), imported definition/usage/context/binding counts, and attempted/prepared/blocked/reused context counts. Start and completion messages use the existing Python logger. No allocation tracing or source-content copies are added for measurement.

These are preparation measurements only. Import time, native conversion time, and a phase-specific peak are not measured. A passed preparation remains `conversion_enabled=false` and `acceptance_complete=false`. Both behavior and assembly native generation/review/compilation/executable behavior acceptance and approved enterprise-scale measurement remain unverified gates. This report cannot enable conversion or certify a production profile.

For a local check, run the scoped acceptance, workflow, closure, and reuse tests with the existing converter regressions. For enterprise acceptance, first identify an approved workspace/vault and record its exact version, profile, selected contexts, and machine/toolchain. Use a fresh run/database/output directory and retain previous compatible binaries, vault, database, and generated outputs together for rollback. Do not migrate old run state in place or clear stale markers. Schema-three intake/preparation is supported; schema-three native conversion remains blocked for every profile until a complete runtime path is verified. Legacy schema support is unchanged.

## Implementation file summary

The current implementation changes these areas only:

| Files | Reason |
| --- | --- |
| `Main.java` | Select opt-in scoped generation and record legacy collision diagnostics |
| `SourceDefinitionIdentity.java`, `ScopedDefinitionCatalog.java` | Preserve exact source occurrences and resolve operation-local and channel scopes |
| `ScopedVaultGenerationService.java`, `VaultManifestWriter.java` | Generate canonical source notes and publish contextual connections, identity, revision and class-origin evidence |
| `ScopedVaultPaths.java`, `JsonOutput.java`, `LinkResolver.java` | Keep deterministic paths, serialized manifests, and note links consistent |
| `LegacyVaultCollisionCheck.java` | Expose legacy overwrite risks without changing legacy generation behavior |
| `OperationFileParser.java`, `FormatFileParser.java`, `ContextFileParser.java` | Parse a selected XML occurrence without choosing another same-name definition |
| `OperationMarkdownWriter.java`, `OpStepMarkdownWriter.java`, `FormatMarkdownWriter.java`, `ContextMarkdownWriter.java`, `JavaClassMarkdownWriter.java` | Use scoped destinations while retaining existing note sections |
| `vault_manifest.py`, `scoped_vault_importer.py`, `vault_importer.py` | Validate scoped input and persist definitions/usages without bare-name merging |
| `closure_builder_tool.py` | Prevent legacy conversion lookups from consuming scoped inventory unsafely |
| `discovery.py`, `operation_calls.py`, root `Excel Generator.py` | Read operation views and the corresponding format/call evidence in both layouts |
| `test_scoped_vault_identity.py` | Validate duplicate names, manifests, import, conversion gating, legacy compatibility, and copied utility execution |
| This guide and the migration plan | Record usage, implemented boundaries, and remaining conversion work |

The packaged Mapper builds successfully with JDK 25. The channel-discovery correction passed all 14 channel and scoped-vault checks, including both link modes and declared-import filtering. The regenerated bank-demo vault at `outputs/bank-demo-scoped-vault-channel-discovery` places the base class under XML resources and preserves all 127 source identities and its eight-operation, three-call graph. No enterprise vault or saved run database was migrated. Existing outputs, work, and unrelated business code were preserved.

The subsequent XML inventory path simplification passed all 15 channel and scoped-vault checks. The latest bank-demo vault is `outputs/bank-demo-scoped-vault-resource-paths`. It preserves all 218 notes and 127 source identities from the preceding vault, with unchanged Java paths, operation-view paths, source provenance, ambiguity diagnostics, and call graph.


## C8 native generation capability

The saved profile defaults to `scoped_native_mode: prepare`. To opt in on a **fresh** scoped run, use:

```yaml
mapper_vault_layout: scoped
source_workspace_id: your-workspace
conversion_strategy: behavior_units
scoped_native_mode: behavior_units_v1
```

Keep the explicit production project/classpath settings described above. The C8 policy fingerprint changes; do not reuse C7 databases with a changed mode. Preserve previous vaults and databases for rollback. The bank-demo validation profile remains preparation-only until C9 acceptance.

Checkpoint resume, behavior conversion, and operation assembly now enter the same qualified native engine. The execution adapter retains original provenance and configuration, maps routing to ordered occurrence IDs, and preserves terminal, self, and backward targets. It carries selected format trees, response-body switches, context, contracts and operation-call evidence into existing generation/review/build/test flows. It does not recreate the whole XML channel or reinterpret legacy name-keyed tables.

The separate `plan_approval_policy` is enforced before Gate 1. Review `conversion_plan.md`/`.json` and use the existing CLI plan decision. Gates 1–4 retain their policies; a pending human gate pauses execution. Native task execution is scoped to the selected contexts and is unavailable outside that invocation. Unsupported native strategies remain blocked. Published API pins and existing preparation blockers remain authoritative.

Accepted model results require exact contextual request fingerprints, C5 checkpoint proof, and unchanged returned-file hashes. Legacy accepted-result compatibility is insufficient. Cached results still pass the existing validators. Freshness is checked before requests, reuse, and acceptance; downstream operation evidence requires a matching qualified native artifact record. Derived POM dependency advice is normalized for request identity; testing pins and actual build validation remain required.

`scoped_workflow_preparation.json` remains input-preparation evidence (`conversion_enabled=false`). `scoped_native_execution.json` separately records the attempted capability, contexts, unit count, phase and elapsed time; `acceptance_complete=false` intentionally does not claim deployment or C9 completion.

C8 tests use deterministic candidate/review responses with real Mapper, Maven, compilation, and executable JUnit on Java 25. Two same-label transformations must execute in source order (412; reversed order gives 421). A separate original-fixture Java oracle checks that distinction. This is not original Composer runtime equivalence or bank-wide native conversion. Full bank-demo measurement, wrapper/package/deployment evidence, and controlled default enablement remain C9 work; existing finalization checks must still pass.


## C9 bank-demo acceptance execution

A fresh C9 validation run is isolated in `outputs/bank-demo-c9-20261025`. Its `acceptance-report.md` and `live-status.json` distinguish completed regression checks from the actual bank-demo live-model conversion. All 10 consuming contexts prepare (83 configured units). The user authorized automatic gates for this local check; the saved run profile records `automatic` decisions rather than claiming manual review. The reusable bank-demo profile and normal approval defaults remain unchanged.

The local continuation process performs actual generation, review and Maven validation; an observer updates its result after process exit. A running process, successful preparation, or green fixture suite does not establish full bank-demo acceptance. The report must show completion of the actual required stages before broader enablement. Keep C9 open while those stages are pending or blocked. Preserve the old vault/database/JAR, use fresh run directories for changed policy, and retain technical validation and runtime-evidence requirements when gates are automatic.
