# Composer Mapper vault hierarchy and identity migration plan

Status: Migration in progress. Scoped Mapper generation, manifest readers, qualified inventory import, and report discovery are implemented as opt-in functionality. Full scoped conversion remains gated pending the converter stages below. See [scoped vault usage and compatibility](../scoped_vaults.md).

## Purpose

Migrate Composer Mapper output from global entity folders to a channel and operation hierarchy. Update the converter and every affected utility to preserve source identity throughout discovery, generation, import, conversion, persistence, planning, and reporting.

Two channels must be able to contain operations with the same name. Two operations must be able to contain steps with the same ID. Different formats, contexts, and Java implementations must be able to share display names without overwriting or resolving to one another.

This is a vault format and identity migration, not a directory rename. Correct folders cannot repair definitions already conflated in memory or subsequently merged by database keys. Implement and release the changes in stages with compatibility gates.

## Problem and current behavior

The enterprise workbook contains operations with zero Calls count and blank waves. One reported issue is `Linked step belongs to another operation; possible Mapper step-ID collision`. Several operations reportedly link to a step with the same local name.

Calls count includes distinct successfully resolved operation connections. Rejected targets are not counted. Therefore, zero calls with an issue does not establish that an operation has no calls. Issues block the affected operation and propagate to its callers, leaving waves blank. An operation with no outgoing calls and no issues should receive wave one.

The collision message establishes a parent mismatch. Confirm a particular overwrite by comparing original XML definitions and their generated links. Do not remove the check to manufacture migration waves.

The repository currently has these relevant assumptions:

- `OpStepMarkdownWriter` writes `opsteps/<step-id>.md` and retrieves parent metadata through a global step-ID map.
- `OperationMarkdownWriter` writes `operations/<operation-id>.md`.
- `XmlDefinitionIndexer` uses bare IDs in operation, step, format, and context maps. Later entries can replace earlier definitions before rendering.
- `Indexes` also contains unqualified operation/channel and relationship maps.
- `LinkResolver` generates links to global entity folders.
- The importer discovers top-level operation, step, format, and context notes; class discovery is recursive.
- Imported source artifact keys combine run, entity kind, and bare logical ID; Java class keys use FQCN. Separate files can still merge in storage.
- Invalidation and downstream queries use logical IDs and need a scope audit.
- Call discovery expects a root `operations` directory. Excel Generator bundles that discovery assumption.

## Goals and boundaries

1. Preserve every original definition occurrence and select the correct definition for each consumer.
2. Organize Markdown by consuming channel and operation.
3. Preserve original IDs, parameters, transitions, source locations, hashes, channel restrictions, and shared-use evidence.
4. Resolve references according to verified channel imports and source precedence, never a global last-write-wins lookup.
5. Distinguish source definitions from operation-specific copies of their notes.
6. Retain legacy input support where identities are unambiguous during transition.
7. Preserve report wave semantics, cycle groups, issue propagation, and standalone utility portability.

Do not change unrelated conversion rules, public service contracts, generated routes, validation, logging, telemetry, review gates, or business execution order. Do not rename source IDs to encode paths. Do not merge definitions merely because their names or contents match.

## Proposed vault hierarchy

```text
vault/
  vault-manifest.json
  analysis/
    channel-operation-registry.md
    unresolved-references.md
    entity-collisions.md
  channels/
    INTERNET/
      channel.md
      operations/
        GetClientOverviewOp/
          operation.md
          opsteps/
            CallIMAX.md
          formats/
          contexts/
          classes/
            <package-path>/
    IVR/
      channel.md
      operations/
        GetClientOverviewOp/
          operation.md
          opsteps/
          formats/
          contexts/
          classes/
    <channel>/
      resources/
        formats/
        contexts/
        classes/
  unassigned/
    resources/
```

Each operation folder contains one `operation.md`, rather than another nested operations folder. Its resources are the resolved definitions it uses, including required transitive dependencies. An operation view does not declare exclusive ownership of those resources.

Channel resource folders preserve inventory definitions without known operation consumers. The proposed unassigned inventory preserves source definitions whose channel cannot be established, with explicit diagnostics. Unknown scope must not silently become a real channel or disappear from inventory. Conversion of operations with unresolved channel identity remains blocked.

Inherited operations have views in consuming channels, with originating definition scope recorded separately. Local overrides select the effective definition using existing verified import rules.

Use original channel, operation, step, and resource names in the folder hierarchy and filenames. Do not append generated IDs or hashes. The channel and owning operation provide the scope for operation views. Java inventory mirrors the source-relative file path with `.java` replaced by `.md`, without extra source-filename or fully qualified class-name directories. XML inventory keeps only the resource origin: `defaultFile/<entity>.md` for defaults, `selfDefOper/<operation-file>/<entity>.md` for operation-file declarations, and the source-file stem for other XML origins. Do not reproduce the project, `src`, XML-definition tree, repeated channel, or XML element selector as directories. Full source paths, selectors, definition identities, and usage identities remain in metadata and the manifest. Keep actual duplicate declarations separate without changing resolution rules or adding filename suffixes.

## Identity contract

### Definition and usage are different

A definition identifies an original source entity independently of its consumers and current contents. A usage identifies that definition as resolved for a consuming operation. A note path is a presentation location, not an identity or proof of ownership.

| Entity | Required scope | Preserved source name |
| --- | --- | --- |
| Operation definition | Workspace, source scope, relative file, exact XML selector | Operation ID |
| Effective operation | Consuming channel and selected operation definition | Operation ID and origin channel |
| Step definition | Owning operation definition and exact step selector | Step ID |
| Format/context definition | Workspace, definition scope, relative file, XML selector | Logical ID |
| Java implementation | Workspace, source root, relative file, package/class and optional method selector | FQCN and method |
| Resource usage | Consuming effective operation and resolved definition | Original resource name |

Use structured records internally and a versioned canonical serialization for persisted keys. Do not concatenate uncontrolled names with ambiguous delimiters. Do not include content hash or machine-specific absolute checkout path in stable identity. Hashes describe revisions. Relocating the same workspace should not invalidate everything solely due to an absolute path change.

The existing Python `SourceImplementationRecord` already separates implementation identity, source coordinates, and revision. The component inventory retains original definition occurrences with XML selectors. Reuse and extend those contracts where appropriate instead of creating a competing identity system.

Same-name resources remain separate unless source identity establishes they are the same definition. Equal contents alone are insufficient. Multiple operation views of a shared definition retain one definition identity and separate usage identities.

### Proposed note metadata

Retain existing fields and add a versioned identity envelope. Finalize the exact schema before implementation; this example is a proposed contract, not implemented output.

```yaml
vault_schema_version: 2
entity_type: opStep
entity_id: CallIMAX
qualified_entity_id: <stable-definition-key>
usage_id: <stable-usage-key>
channel: INTERNET
operation_id: OperationA
operation_identity: <effective-operation-key>
definition_channel: COMMON
source_workspace_id: <stable-workspace-key>
source_relative_path: <relative-source-file>
source_selector: <exact-definition-selector>
source_hash: <content-revision>
```

Keep legacy `used_by_operations` while adding qualified consumer references. Obtain step ownership directly from its parsed parent. Shared resources retain qualified consumers or manifest usages. Existing absolute `source_file` may remain as provenance but must not be the stable key.

The frontmatter parser supports a small YAML subset. Emit supported scalar/list fields or explicitly extend and test parsing. Do not introduce nested metadata that readers silently discard; richer relations can live in the manifest.

### Manifest

The manifest records schema/producer versions, identity encoding, stable workspace identity, generation scope, selected channels, import provenance, and entity views. Entries record definition key, usage key, kind, consuming operation, note path, source coordinates, hash, and resolved edges.

Readers validate paths remain inside the vault, reject conflicting identities, and ensure repeated views agree on source identity and revision. The manifest distinguishes complete inventory from partial generation. Generate into staging and publish completion only after required notes and references validate. Unknown future schema versions must fail clearly.

## Resolution and sharing rules

Resolve source definitions before rendering their operation views:

1. Establish consuming channel and declared imports.
2. Select the effective operation using verified registration and override semantics.
3. Resolve step references only inside their owning operation definition.
4. Resolve inline and external resources using verified source precedence and eligible scopes.
5. Resolve classes using effective tag mappings and source roots; FQCN alone cannot select among distinct implementations.
6. Record selected definition, consumer, and provenance on every resolved edge.
7. Report missing or ambiguous references with candidate source coordinates, without global fallback.

Verify detailed precedence for inline formats, channel resources, imported resources, context inheritance, and Java roots against supported Composer behavior. Do not invent precedence during the migration. Distinguish legitimate local overrides from duplicate definitions at the same effective scope.

Materialize one resource view per definition usage within an operation. Repeated references reuse it. Distinct definitions sharing a display name receive deterministic filenames. Traverse transitive dependencies with visited sets keyed by definition and usage context; retain cycle diagnostics. Preserve unreferenced definitions in inventory.

Shared class notes retain cross-operation usage evidence. Copying a note into multiple folders must not create multiple independent conversions or shared libraries for one implementation. Existing ownership and reuse policies continue to govern generated code.

### Prove Java class origin before declaring sharing

Matching class names, FQCNs, contents, or operation-folder copies do not establish a shared implementation. Each operation's class reference must first resolve against its actual source roots, dependencies, classpath ordering, and applicable classloader or module boundaries. Channel identity alone is not enough to establish that environment.

Record resolution evidence per usage: consuming operation, effective project/module, ordered eligible source roots and dependency entries, candidate definitions, selected origin, and the rule that selected it. For source classes, retain workspace identity, source root, relative file, and definition selector. For binary classes, retain the originating dependency identity, artifact revision or digest, and class entry within the archive or directory. Record source and binary origins separately when both are available; a same-name source file is not automatically proof of the loaded binary's origin. Keep content revisions separate from stable definition identity.

Declare source-definition sharing only when usages resolve to the same canonical originating definition. Same-FQCN classes from different roots or dependencies remain distinct even if their bytes match. Equivalent artifact copies may share a canonical dependency origin only when artifact identity and revision are verified; matching filenames or coordinates without revision evidence are insufficient. Never select a global first match merely because it appears in the workspace.

If project metadata establishes deterministic classpath precedence, record that selection and any shadowed candidates. If the effective order, classloader boundary, dependency origin, or source-to-binary relationship cannot be established, report unresolved or ambiguous resolution and block affected conversion or reuse decisions. Do not infer sharing. The Mapper may emit candidates for the converter to resolve, but such entries must be explicitly unresolved until the converter records sufficient evidence.

Sharing an originating definition also does not by itself authorize reusing generated code. Existing reuse checks must additionally validate revision and relevant conversion context, including resolved dependencies and effective mappings. A changed resolution environment must invalidate affected resolution evidence and reuse decisions even when the class's own source hash is unchanged.

## Link contract

Centralize paths and links for Steps, transitions, formats, context inheritance, classes, shared components, operation calls, channel summaries, and analysis references. Keep Markdown and Obsidian modes.

Continue the existing vault-root convention for machine-consumed links, document it, and validate supported viewer behavior. Readers must not guess when root and relative candidates resolve to different notes. Handle escaping, Unicode, spaces, fragments, traversal, and safe filenames consistently.

Transitions resolve only within the parent operation. Cross-operation calls remain operation dependencies. Preserve `opExecuteName` as source evidence and record the qualified resolved target separately. Preserve caller-channel behavior and explicit cross-channel resolution requirements unless independently verified source semantics require a change.

## Mapper implementation

### Channel discovery correction

The ownership issue was in discovery: XML was already recognized as a channel, but Java files alongside its XML definitions were marked unassigned. Discovery now associates those Java files with the source folder's declared channel before filtering. Existing scoped generation consumes that channel metadata for resource placement and candidate filtering. This correction does not require another vault hierarchy, writer, or converter change.

Use the actual declaration structure to establish channel names and their source scope:

```text
<project>/src/
  com/.../<JavaClass>.java
  Xml Definition/
    Channel/
      <channel-name>/
        dse.ini
        defaultFile/
          dsecontext.xml
          dsedata.xml
          dseformat.xml
          dseoperation.xml
        selfDefOper/
          <operation>.xml
```

First discover channel declarations and associate each declaration with its containing source folder. Obtain the channel name from the declared channel directory, not from the project name. Files already inside a channel directory retain their directly detected channel. Java source files elsewhere beneath the associated source folder receive that channel through the source-folder association. Complete this association before applying the selected-channel and declared-import filters.

Channel definitions establish availability: operations and the formats, contexts, steps, mappings, and other definitions declared in their XML files belong to their existing channel scope. Java classes and packages in the associated source folder are available to that channel. Availability alone does not establish an operation dependency, prove classpath selection, or authorize implementation reuse. Preserve those existing distinctions.

For the reported bank-demo case, `WSBCC_XML/src/Xml Definition/Channel/XML/dse.ini` establishes XML as the channel for the source folder. Its base Java class should consequently appear under `channels/XML/resources/classes/WSBCC_XML/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.md`, rather than under unassigned. Preserve the current Java inventory path convention; change only its channel placement.

#### Expected files to change:

- [FileDiscoveryService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/FileDiscoveryService.java): discover declaration-to-source-folder associations and assign channel metadata before filtering. Preserve the public discovery methods and existing direct channel detection.
- [test_mapper_channel_imports.py](../../source/tests/test_mapper_channel_imports.py): verify Java sources alongside XML definitions receive the declared channel and selected-channel/import filtering remains correct.
- [test_scoped_vault_identity.py](../../source/tests/test_scoped_vault_identity.py): verify the XML base class lands in XML resource inventory with its existing readable filename and source identity.
- [Scoped vault usage guide](../scoped_vaults.md): describe declaration-based source ownership when the correction is implemented.
- This plan: record the correction and its validation result.

Implementation sequence: add the focused discovery cases, update source-folder channel association, run discovery/import and scoped-vault regressions, rebuild the Mapper, and regenerate the bank demo. Validate that the XML base class moves to XML resources, operation-call relationships remain correct, and original names and canonical source definition identities remain unchanged.

Completed validation: the Mapper package rebuilt successfully and all 14 channel-discovery and scoped-vault checks passed. A fresh bank-demo vault at `outputs/bank-demo-scoped-vault-channel-discovery` places the base class under XML resources, retains all 127 source definition identities and the eight-operation, three-call graph, and has no Java inventory left unassigned. Previous outputs and work were preserved.

Do not change index semantics, resource resolution rules, classpath evidence requirements, source project structure, operation-view paths, legacy naming, or the converter gate for this correction. Files whose ownership is not established by the discovered declarations must not be assigned by guessing their project name.

### Discovery and indexes

Carry source channel/root, relative file, and definition selector from discovery through parsing and indexing. Replace global single-value name maps with occurrence-preserving indexes and contextual resolvers. Name indexes remain useful for search, but cannot choose definitions.

Update operation registration, channel mappings, tag mappings, step ownership, and class/format/context usage edges. Audit XML, INI, and Java indexes. Same-name operations across channels must survive before any files are written. Diagnose ambiguity instead of accepting last-write-wins behavior.

### Models and writers

Add focused definition, effective-operation, and usage records. Writers receive resolved context rather than rediscovering ownership by name. Preserve public signatures through adapters where practical, but ambiguous old calls must fail rather than silently discard scope.

Render each operation view from a resolved graph. Preserve every existing note section, parser warning, attribute, and source hash. Put path construction in one service shared by writers and link generation. XML behavior remains unchanged apart from capturing scope and selectors.

### Output lifecycle and compatibility option

Introduce explicit layout selection during transition, proposed as `--vault-layout legacy|scoped`. Keep the current default until downstream gates pass. Legacy mode must report collisions instead of silently overwriting; choose its exact failure policy in stage zero.

Generate scoped output into a fresh destination. Do not move old files as a migration strategy. Scope cleanup to generated output, preserve user notes and old runs, and validate deterministic regeneration and orphan handling. Partial output must not publish a completed manifest.

## Converter and persistence implementation

### Import and parsing

Create schema-aware discovery shared by import and report code. Schema two uses manifest entries and canonical identities. Legacy input retains its old parsing rules with ambiguity checks. Folder depth must not define identity.

Validate metadata, manifest, source evidence, and parent links agree. Import every operation usage, deduplicate canonical source definitions, and persist usage edges separately. Read channel notes and registries from new locations without guessing scope from filename.

Separate definition counts from usage/view counts where copies would otherwise inflate inventory summaries. Preserve useful existing summaries while documenting any changed count meaning.

### State and API boundaries

Audit source artifacts, operations, channel operations, native/generated artifacts, registries, requirements, tasks, review evidence, call graphs, and invalidation events. Add qualified keys and usage relationships through an explicit schema migration or additive tables. Preserve original logical IDs as business labels.

Do not globally replace every logical ID with an opaque key. Some APIs intentionally accept source names. Resolve at explicit boundaries; ambiguous unqualified requests require channel/operation context. Legacy adapters are safe only where scope is unambiguous.

Carry operation channel through planning and execution. Cache/reuse lookups need definition identity, relevant revision, and usage context where required. Truly shared implementations remain eligible for existing reuse behavior.

### Closure and conversion

Update format resolution, context fields/hierarchy, Java implementation lookup, behavior units, routing, assembly, and service generation. Preserve source step IDs in flow semantics while using scoped internal keys. Dependency closure must follow the selected definition rather than any same-name record.

Internal identity migration is not authorization to change public service routes, request/reply formats, or saved service contracts. Validate any mappings needed for pinned APIs explicitly.

### Invalidation and resume

A shared definition revision invalidates all dependent usages. A local change must not invalidate an unrelated same-name definition. Folder relocation alone is not a source content change. Review evidence and caches must use the appropriate identity and revision.

Record vault schema, identity version, and manifest digest in run state. Never silently resume an old run against a new identity model. Recommended first rollout: new runs for scoped vaults; retain old vault/database pairs for legacy resume. Cross-version resume requires separately validated source-backed mapping; ambiguous records require regeneration and re-review.

## Excel and other utilities

Update shared call discovery to find schema-two operation roots and use resolved step identities. Preserve distinct direct call counts, all call sites, dependency-first waves, cycle groups, and transitive unresolved blocking.

Update the repository exporter and single-file Excel Generator in the same compatibility release. Bundle the new reader/discovery in the standalone file without Snapir imports. Retain Python/openpyxl requirements, positional vault input, output override, and optional Relationships sheet.

Following nested step links alone is insufficient for the broader migration: operation discovery and identity also change. Explicitly support legacy and scoped inputs and reject unknown schemas. Verify the copied utility outside the repository. Preserve report business columns unless ambiguity requires a documented addition; compare logical contents allowing intentional evidence-path differences.

Audit external scripts, inspection tools, prompts, examples, evidence readers, and enterprise consumers. A Mapper build passing is not proof of system compatibility.

## Expected files to change:

Only this plan changes now. The inventory below describes expected future implementation areas. Each implementation stage must declare its exact file list before editing. Proposed new files are labeled. Expand the inventory when the consumer audit finds additional dependencies; do not use it as permission for unrelated cleanup.

### Mapper indexes and models

- [Indexes.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/Indexes.java): scoped definitions and usages.
- [IndexBuildService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/IndexBuildService.java): source/channel-aware index construction.
- [XmlDefinitionIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/XmlDefinitionIndexer.java): preserve occurrences and qualified relationships.
- [IniMappingIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/IniMappingIndexer.java): scoped registration and effective mappings.
- [JavaClassIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/JavaClassIndexer.java): source-aware implementation identity.
- [DiscoveredFile.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/DiscoveredFile.java): source scope propagation if existing fields are insufficient.
- [OperationDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/OperationDef.java), [OpStepDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/OpStepDef.java), [FormatDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/FormatDef.java), [ContextDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/ContextDef.java), and [JavaClassDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/JavaClassDef.java): source coordinates and identity metadata without renaming source IDs.
- Proposed new [SourceDefinitionIdentity.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/SourceDefinitionIdentity.java) and [EntityUsage.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/EntityUsage.java): shared definition and consumer records.

### Mapper parsing and resolution

- [FileDiscoveryService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/FileDiscoveryService.java) and [ChannelImportResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/ChannelImportResolver.java): source and effective channel scopes.
- [OperationFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/OperationFileParser.java), [FormatFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/FormatFileParser.java), [ContextFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/ContextFileParser.java), and [JavaClassParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/JavaClassParser.java): selectors and ownership where required.
- Proposed new [ScopedDefinitionResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/ScopedDefinitionResolver.java): context-specific lookup and ambiguity diagnostics.

### Mapper output

- [StreamingGenerationService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/StreamingGenerationService.java): operation views, inventory, channel summaries, manifest publication.
- [LinkResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/LinkResolver.java): qualified links in both modes.
- [OperationMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/OperationMarkdownWriter.java), [OpStepMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/OpStepMarkdownWriter.java), [FormatMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/FormatMarkdownWriter.java), [ContextMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/ContextMarkdownWriter.java), and [JavaClassMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/JavaClassMarkdownWriter.java): scoped paths, identity, preserved sections.
- [ScopedVaultPaths.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/ScopedVaultPaths.java): original-name channel and operation paths; definition identities remain in metadata. Legacy safe-name handling is unchanged.
- [VaultPreparationService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/VaultPreparationService.java): layout-aware safe output preparation.
- [Main.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/Main.java) and [Args.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/Args.java): transition option and compatibility messages.
- Proposed new [VaultPaths.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/VaultPaths.java) and [VaultManifestWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/VaultManifestWriter.java): central path contract and manifest serialization.

### Python models and import

- [composer.py](../../source/models/composer_models/composer.py) and [source_component_identity.py](../../source/models/source_component_identity.py): aligned identity metadata.
- [vault_reader.py](../../source/tools/composer_mapper_tools/vault_reader.py) and [vault_importer.py](../../source/tools/composer_mapper_tools/vault_importer.py): schema-aware discovery, import, deduplication.
- [frontmatter_parser.py](../../source/tools/composer_mapper_tools/frontmatter_parser.py), [operation_parser.py](../../source/tools/composer_mapper_tools/operation_parser.py), [opstep_parser.py](../../source/tools/composer_mapper_tools/opstep_parser.py), [format_parser.py](../../source/tools/composer_mapper_tools/format_parser.py), [context_parser.py](../../source/tools/composer_mapper_tools/context_parser.py), and [java_class_parser.py](../../source/tools/composer_mapper_tools/java_class_parser.py): qualified identity and source metadata.
- [channel_note_parser.py](../../source/tools/composer_mapper_tools/channel_note_parser.py) and [channel_registry_parser.py](../../source/tools/composer_mapper_tools/channel_registry_parser.py): qualified channel references.
- Proposed new [vault_manifest.py](../../source/tools/composer_mapper_tools/vault_manifest.py) and [entity_identity.py](../../source/tools/composer_mapper_tools/entity_identity.py): manifest validation and common identity resolution.
- [definitions.py](../../source/tools/component_inventory_tools/definitions.py) and [inventory.py](../../source/tools/component_inventory_tools/inventory.py): align existing occurrence-preserving inventory.

### Persistence and converter consumers

- [schema.py](../../source/tools/state_store_tools/schema.py), [source_artifacts.py](../../source/tools/state_store_tools/source_artifacts.py), [channel_operations.py](../../source/tools/state_store_tools/channel_operations.py), [native_java_artifacts.py](../../source/tools/state_store_tools/native_java_artifacts.py), and [generated_artifacts.py](../../source/tools/state_store_tools/generated_artifacts.py): scoped keys and usage relations.
- [invalidation.py](../../source/tools/state_store_tools/invalidation.py) and [invalidation_events.py](../../source/tools/state_store_tools/invalidation_events.py): qualified dependency invalidation.
- [closure_builder_tool.py](../../source/tools/conversion_tools/closure_builder_tool.py), [closure_validator_tool.py](../../source/tools/conversion_tools/closure_validator_tool.py), [format_dependency_resolver_tool.py](../../source/tools/conversion_tools/format_dependency_resolver_tool.py), [context_hierarchy_resolver_tool.py](../../source/tools/conversion_tools/context_hierarchy_resolver_tool.py), [context_field_resolver_tool.py](../../source/tools/conversion_tools/context_field_resolver_tool.py), [java_impl_resolver_tool.py](../../source/tools/conversion_tools/java_impl_resolver_tool.py), and [operation_call_closure.py](../../source/tools/conversion_tools/operation_call_closure.py): contextual dependency resolution.
- [component_registry.py](../../source/tools/artifact_registry_tools/component_registry.py) and [reuse_resolver.py](../../source/tools/artifact_registry_tools/reuse_resolver.py): correct reuse across usages without merging distinct definitions.
- [checkpoints.py](../../source/runtime/checkpoints.py), [behavior runner](../../source/runtime/behavior_conversion/runner.py), [assembly runner](../../source/runtime/operation_assembly/runner.py), and [shared library registry](../../source/runtime/shared_libraries/registry.py): identity propagation, ownership, and resume audit.
- [planning agent](../../source/agents/migration_planning/agent.py) and [batch_composition.py](../../source/agents/migration_planning/batch_composition.py): preserve channel during same-name operation selection.

### Reports and documentation

- [discovery.py](../../source/tools/operation_call_tools/discovery.py), [preflight.py](../../source/tools/operation_call_tools/preflight.py), and [operation_calls.py](../../source/tools/state_store_tools/operation_calls.py): schema-aware graph evidence and persistence.
- [export_operation_migration.py](../../source/export_operation_migration.py) and [Excel Generator.py](../../Excel%20Generator.py): dual-layout input and updated standalone bundle. Change wave or workbook writers only if the qualified graph contract requires it.
- [running_migrations.md](../running_migrations.md), [operation_calls.md](../operation_calls.md), and [architecture_v3.md](../architecture_v3.md): release-time compatibility, regeneration, and deployment instructions.

### Validation files

- [test_composer_mapper_tools.py](../../source/tests/test_composer_mapper_tools.py), [test_mapper_channel_imports.py](../../source/tests/test_mapper_channel_imports.py), [test_operation_calls.py](../../source/tests/test_operation_calls.py), and [test_component_inventory.py](../../source/tests/test_component_inventory.py): import, source inventory, channel, graph coverage.
- [test_dependency_resolvers.py](../../source/tests/test_dependency_resolvers.py), [test_complete_conversion_closure.py](../../source/tests/test_complete_conversion_closure.py), [test_invalidation_e2e.py](../../source/tests/e2e/test_invalidation_e2e.py), and [test_shared_library_planning.py](../../source/tests/runtime/test_shared_library_planning.py): resolution, conversion, invalidation, sharing coverage.
- Proposed new [test_scoped_vault_identity.py](../../source/tests/test_scoped_vault_identity.py) and [test_excel_generator_standalone.py](../../source/tests/test_excel_generator_standalone.py): identity acceptance and portable utility regression coverage.

## Implementation sequence

### Stage zero contract and consumer audit

Finalize schema, canonical identity encoding, the original-name hierarchy, precedence, legacy collision failure policy, and resume policy. Audit folder globs, hard-coded paths, maps, SQL joins, caches, prompts, examples, scripts, and external consumers. Map each affected lookup to a stage and acceptance case.

Define how effective Java source/classpath environments are established for each operation, which evidence the Mapper supplies, and which evidence the converter must complete. Include manifest fields for resolution status, origin, environment fingerprint, and selection provenance. Establish explicit handling for unavailable build metadata, multiple classloaders, shadowed candidates, and binary-only dependencies.

Gate: example identities for same-name channels/operations/resources and shared imported definitions resolve unambiguously. Record unresolved source semantics before coding the resolver.

### Stage one source identity and resolution

Implement definition/usage records and scoped indexes behind existing output interfaces. Preserve all source occurrences. Align with the existing Python inventory contract. Test imports, overrides, Java roots, and ambiguity handling before changing folders.

Gate: distinct definitions survive in memory and every test edge selects the expected source coordinates.

### Stage two scoped Mapper generation

Implement manifest, paths, all operation/resource views, links, inventory output, and completion publication. Add opt-in scoped output and controlled legacy behavior. Preserve existing note sections.

Gate: no unintended overwrites; complete inventory; valid links; correct parents/provenance; deterministic output in both link modes.

### Stage three reader and persistence compatibility

Implement schema detection, manifest reader, metadata parsing, qualified storage, usage deduplication, and legacy adapters. Introduce database version and resume checks. Keep the new output default disabled.

Gate: both input versions import correctly; definition/usage counts reconcile; ambiguous legacy records are diagnosed rather than merged.

### Stage four converter and utilities

Update closure, resource lookup, planning, assembly, component reuse, evidence, caches, and invalidation. Audit agent/tool inputs so qualified scope survives every boundary. Preserve external contracts.

Gate: distinct same-name entities convert correctly; real shared definitions retain reuse; unrelated namesakes remain isolated; stale/incompatible runs cannot resume silently.

### Stage five Excel and enterprise portability

Update graph discovery, preflight, persistence, repository exporter, and standalone utility. Test both layouts and copied-file execution outside the repository.

Gate: independently specified graph edges, counts, cycles, and waves match. Collision-free legacy and scoped reports agree on business values.

### Stage six rollout

Build a coordinated compatible Mapper/converter/utility release. Regenerate enterprise vaults from original source into new destinations. Preserve old vault/database pairs. Document exact compatible artifact versions. Switch the default only after all consumer gates pass.

Gate: enterprise-sized rehearsal passes reconciliation, link checks, representative conversion, report checks, and agreed performance limits.

## Validation matrix

| Case | Required result |
| --- | --- |
| Same operation ID in two channels | Separate effective operations, views, storage keys, and correct call targets |
| Same step ID across operations/channels | Correct owner, parameters, transitions, and evidence for each occurrence |
| Duplicate step ID inside one operation with disjoint `onlyFor` conditions | Preserve separate source occurrences and select the applicable variant per consuming channel; no silent overwrite |
| Multiple same-ID steps applicable to one channel | Separate ordered occurrences; inclusive named lookup from current index, then wrap to the beginning; no duplicate-label rejection |
| Same format/context name, different sources | Correct scoped selection, conversion, and isolated invalidation |
| Inline/external names overlap | Verified source precedence and recorded provenance |
| Imported definition with local override | Effective override selected without losing original source identity |
| One definition used by many operations | Multiple views/usages, one definition, preserved shared conversion |
| Same FQCN in different source roots | Distinct implementation identities and contextual selection |
| Same FQCN supplied by different dependencies | Selected origin follows the verified operation environment; unrelated origins never merge |
| Three operation views referencing one proven origin | One definition with three usages; reuse still checks revision and conversion context |
| Same FQCN and identical bytes from different origins | No inferred source-definition sharing from content equality |
| Known classpath order shadows another candidate | Selected origin, ordering rule, and shadowed candidate recorded |
| Missing classpath order or classloader evidence | Explicit unresolved/ambiguous status; no arbitrary selection or reuse |
| Same-name source and binary with unproven correspondence | Source is not substituted as the binary's origin without evidence |
| Dependency order changes without a class source change | Resolution evidence and affected reuse decisions invalidated |
| Unreferenced definitions | Preserved inventory and reconciled counts |
| Java source beside a declared channel's XML definitions | Associated with that source folder's declared channel before channel/import filtering |
| XML project's base operation class | Stored under XML resource inventory with the current readable package path, not unassigned |
| Resource dependency cycle | Finite traversal and actionable diagnostic |
| Operation and step filenames | Original names with no generated ID or hash suffix |
| Separate XML inventory occurrences | Short defaultFile or selfDefOper origin folders preserve declarations; full provenance stays in metadata |
| Workspace relocated | Stable source identity when relative source structure remains unchanged |
| Unresolved call target | Issue retained and affected callers blocked |
| No calls and no issues | Zero Calls count and wave one |
| Repeated call sites | One direct connection with all evidence preserved |
| Operation call cycle | Existing stable grouping and wave behavior preserved |
| Collision-free legacy vault | Supported current behavior retained |
| Overwritten legacy vault | Diagnostic and source regeneration requirement |
| Unknown/partial/conflicting manifest | No successful conversion of silently incomplete input |
| Regeneration/interruption | No stale views or completed manifest for partial output |
| Shared source revision changes | All dependents invalidated, unrelated namesakes preserved |
| Cross-version resume | Explicit compatibility failure or validated migration |
| Standalone copied utility | Runs with declared dependency and vault input alone |

Run relevant existing Python regressions and the Maven build alongside acceptance cases. Use temporary destinations, not existing evidence vaults or databases. Assert identity, selected source coordinates, edges, and conversion results, not only folder existence. Measure generated size and time on representative input because per-operation views duplicate shared note content.

## Recovery and rollback

Keep original source, vaults, and databases before rollout. Regenerate scoped output from original XML, INI, and Java. Moving legacy files cannot restore overwritten definitions.

Rollback uses the compatible legacy Mapper, converter, and utility set with matching old vault/database pairs. Do not feed scoped output to a legacy importer. Keep scoped runs separate until a source-backed state migration is implemented. Discard failed generated staging output only within its verified destination; preserve user material and unrelated workspaces.

## Risks and stage zero decisions

- Confirm Composer resource precedence and imported override semantics before implementing scoped lookup.
- Establish operation-specific Java classpath and source-origin evidence before declaring implementations shared; folder placement, FQCN, and content equality are insufficient.
- Choose stable workspace identity, exact selectors, canonical serialization, and revision behavior.
- Finalize manifest schema and unassigned inventory; preserve original names without generated suffixes.
- Define legacy collision failure policy and initial layout default.
- Decide whether cross-version resume is required for the first release; recommended initial policy is separate fresh runs.
- Measure note duplication cost before default rollout; future reference optimizations must preserve the operation-centered view.
- Protect public APIs and pinned contracts from indiscriminate internal key substitution.
- Inventory external enterprise utilities before switching the default.

## Completion criteria

All definitions survive discovery and rendering. All supported consumers understand schema and identity. Same-name entities remain distinct through persistence and conversion. Shared definitions retain ownership and reuse. Excel produces correct calls, issues, cycles, and waves from the new layout. Compatible distribution artifacts, enterprise regeneration instructions, documentation, and rollback verification are delivered together.

Implementation tracking: the initial implementation adds occurrence-preserving scoped generation in a separate service, reuses existing parsers and writers through exact-occurrence parsing and scoped destinations, and keeps legacy output as the default. Qualified inventory import and Excel discovery support the manifest. Closure conversion explicitly rejects scoped runs until its remaining consumers are migrated. Existing enterprise vaults and run databases are not rewritten. These milestones do not satisfy the full completion criteria above.

XML inventory paths now retain only the short resource origin described above. All 15 channel and scoped-vault checks passed after this change. The regenerated bank-demo vault at `outputs/bank-demo-scoped-vault-resource-paths` preserves all 218 notes and 127 source identities from the preceding channel-discovery vault; Java and operation-view paths, provenance metadata, resource diagnostics, and the eight-operation, three-call graph remain unchanged. Existing outputs and work were preserved.

### Follow-up: channel-specific same-ID step variants

Enterprise source confirmed repeated step IDs distinguished by `onlyFor` within one operation. Scoped generation now selects applicable steps using the consuming channel, preserves original order and IDs, and retains unused source variants in inventory. Same-ID inventory variants use readable `onlyFor` folders when needed. Both Excel discovery implementations now match channel restrictions without case sensitivity. The combined scoped and operation-call regression suite passed 36 tests, and the Mapper package rebuilt successfully.

The converter design must preserve these occurrences through import, closure, behavior units, routing, reuse, and freshness. It must consume the selected operation usages without reintroducing excluded inventory definitions. The [converter implementation plan](scoped_vault_converter_implementation_plan.md#channel-specific-step-variants) specifies these requirements and acceptance cases. Converter implementation remains gated and has not been enabled by this follow-up.

### Correction: repeated labels within the same effective flow

Further enterprise XML and runtime screenshots establish that opStep IDs are labels, not unique occurrence keys, even after channel filtering. The execution method passes the current index to named lookup, which searches inclusively from that position and then from the beginning. `next` advances; `end` terminates; a missing name returns `-1`. Equal names are matched exactly. Self-jumps and backward jumps are supported. This supersedes the earlier same-channel duplicate-conflict assumption.

Scoped generation must preserve each source selector and ordered occurrence, using readable occurrence folders only where repeated labels would otherwise overwrite notes. Unique labels keep their paths. Manifest operation entries expose ordered `step_notes` and `entry_step_note`; step entries expose zero-based `step_index` and `transition_targets`. Diagram nodes and transition links distinguish occurrences. Inventory retains unused occurrences without merging them. The converter must carry these identities and ordered targets into closure, behavior units, assembly, and freshness without implementation work being enabled by this document update.
