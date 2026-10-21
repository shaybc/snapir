# Scoped Composer Mapper vaults

Scoped output is an opt-in implementation of the vault hierarchy migration. It preserves source definition occurrences and writes channel and operation views with a versioned manifest. The legacy layout remains the default.

## Current compatibility

| Consumer | Scoped support |
| --- | --- |
| Composer Mapper | Opt-in generation into an empty destination |
| Excel Generator and repository operation exporter | Manifest validation, operation discovery, calls and migration waves |
| Vault inventory import | Qualified definitions and usages in separate tables; channel operations and format contracts |
| Full conversion | Explicitly gated pending qualified closure, reuse, review, invalidation, and resume support |

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

The destination must be empty and outside the source tree. Use the same workspace ID when moving the same source workspace to another machine; use different IDs for independent source workspaces. An optional `--channel INTERNET` selects that channel's effective definitions and declared imports.

Folder and file names retain their original names without generated ID or hash suffixes. Effective operations live under `channels/<channel>/operations/<operation>/operation.md`, with steps and used resources beside them. For example, a step is `channels/INTERNET/operations/GetClientOverviewOp/opsteps/OverviewRefreshLinks.md`. Full identities remain in the manifest and metadata.

Unselected, shadowed, ambiguous, and unreferenced source occurrences remain in channel or unassigned resource inventory folders. Java class inventory mirrors the source-relative file path, replacing `.java` with `.md`; it does not add a source-filename folder or fully qualified class-name folder. Channel ownership places the base class at `channels/XML/resources/classes/WSBCC_XML/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.md`.

XML inventory uses a short resource-origin hierarchy. A context in the defaults file is `channels/IVR/resources/contexts/defaultFile/<context>.md`; a context in an operation file is `channels/IVR/resources/contexts/selfDefOper/<operation-file>/<context>.md`. Other XML files use their file stem as the origin folder. The project path, `src`, XML-definition path, repeated channel, source-file extension, and XML element selector are not reproduced as directories. Original source paths and selectors remain in the manifest and note metadata. Duplicate declarations remain separate, with existing ambiguity diagnostics unchanged.

Nested named `fmtDef` inventory notes use their nearest named parent format and document-order position. Top-level format paths are unchanged. For the two switch blocks in `Alt_GAC4.xml`, the layout is:

```text
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt.md
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt/nested/1/GAC4HostSeSwitchCaseFmt.md
channels/XML/resources/formats/selfDefOper/Alt_GAC4/GAC4HostSeFmt/nested/2/GAC4HostSeSwitchCaseFmt.md
```

Each named format directly owned by a parent gets a one-based ordinal across intervening XML wrappers, regardless of whether its ID repeats. Formats nested inside that child start a new parent scope and extend the same layout recursively. Original IDs, switch criteria, child order, and `refFmt` values remain intact in the generated structure; the two same-ID blocks are not merged or treated as interchangeable definitions.

Nested inventory manifest entries include `parent_definition_id`, `parent_source_selector`, and the one-based `nested_format_index`. Definition identity remains the existing digest of workspace, kind, source-relative file, and exact XML selector; Markdown path allocation does not change that identity. The parent definition can have an operation-view note instead of an inventory note when selected by an operation, so consumers must follow its canonical ID rather than assume a parent inventory file exists. Existing reference-resolution rules are unchanged; this layout does not introduce a new global winner for an ambiguous ID. Legacy output is unchanged. Regenerate into a fresh vault to adopt the layout.

The completed manifest identifies source file and XML occurrence independently of content revisions. Multiple views of one definition retain one definition key and separate usage keys. Do not edit generated notes without regenerating the manifest: consumers reject notes whose hashes no longer match. Interrupted generation retains an incomplete marker and cannot be consumed as a complete vault. Generate a new vault to retry; this mode does not delete previous output.

## Channel ownership

Channel discovery reads the declaration at `<project>/src/Xml Definition/Channel/<name>/dse.ini`. The channel directory supplies the name; the project name is not used to guess it. Java files beneath that same `src` folder receive the declared channel even when they are outside the XML definition tree. Files already inside a channel directory retain their direct channel assignment. Source-folder ownership is established before selected-channel and declared-import filtering.

This lets the existing mapper place the XML project's base operation class under XML resource inventory instead of unassigned. It does not change the inventory path convention, operation dependencies, classpath evidence rules, or converter compatibility gate.

## Java class origin

Java references retain candidate origins and `unresolved_classpath` status. A unique source candidate can be rendered as evidence, but is not asserted to be the implementation loaded by the operation. Equal FQCNs, bytes, or note copies do not establish sharing. Multiple candidates remain separate inventory definitions. Classpath selection and generated-code reuse require additional converter resolution evidence.

## Generate Excel

The standalone file still requires only Python 3.10 or newer and openpyxl:

```powershell
python -m pip install openpyxl
python "Excel Generator.py" "C:\Mapper\scoped-output" --output "C:\Reports\migration.xlsx" --include-relationships
```

Copy the entire generated vault, including its manifest, alongside access to the standalone utility. Excel does not require the original Composer source files. Calls and waves describe resolved operation-call relationships; they do not certify that format dependencies or Java classpaths are ready for conversion.

## Import and resumption

Scoped import stores canonical occurrences in `scoped_source_definitions` and views in `scoped_entity_usages`. It does not project them into the legacy bare-name source artifact table. Existing converter closure creation rejects scoped runs explicitly rather than selecting arbitrary namesakes. Saved operation contracts read format evidence from the selected operation view.

Do not replace a legacy run with scoped input. Reimporting identical scoped evidence is allowed; changed evidence requires a fresh run. Preserve original vault/database pairs for existing legacy resume. Source overwrites in old vaults can only be recovered by regeneration from the original source.

See the [migration plan](plans/composer_mapper_vault_hierarchy_migration_plan.md) for remaining converter stages and rollout gates.

## Implementation file summary

The current implementation changes these areas only:

| Files | Reason |
| --- | --- |
| `Main.java` | Select opt-in scoped generation and record legacy collision diagnostics |
| `SourceDefinitionIdentity.java`, `ScopedDefinitionCatalog.java` | Preserve exact source occurrences and resolve operation-local and channel scopes |
| `ScopedVaultGenerationService.java`, `VaultManifestWriter.java` | Generate isolated operation/resource views and publish identity, revision, usage, and class-origin evidence |
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
