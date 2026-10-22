# Scoped Composer Mapper vaults

Scoped output is an opt-in implementation of the vault hierarchy migration. It preserves source definition occurrences and writes canonical source notes with versioned consuming-channel connections. The legacy layout remains the default.

## Current compatibility

| Consumer | Scoped support |
| --- | --- |
| Composer Mapper | Opt-in generation into an empty destination |
| Excel Generator and repository operation exporter | Manifest validation, operation discovery, calls and migration waves |
| Vault inventory import | Existing schema-two input only; shared schema-three input is explicitly rejected pending converter work |
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

The destination must be empty and outside the source tree. Use the same workspace ID when moving the same source workspace to another machine; use different IDs for independent source workspaces. An optional `--channel INTERNET` selects that channel's effective definitions, its implicit XML base, and declared imports.

Schema-three output writes each source definition once. Declared operations live at `channels/<definition-channel>/operations/<operation>/operation.md`; their canonical step notes include all source occurrences. Shared formats, contexts and Java candidates live in their source channel's resource inventory, using the existing resource-origin layout. Inline operation-owned resources use `resources/owners/<operation>/...` to keep same-label definitions in different operations separate. Nested format folders and original source selectors remain unchanged.

For example, SME's call to XML-defined `POB1Op` points to `channels/XML/operations/POB1Op/operation.md`. No `channels/SME/operations/POB1Op` copy is generated. The `operation_contexts` array records SME's selected step notes, entry step, transition targets, resource references, Java candidate evidence and operation calls. Canonical note annotations describe source/default evidence; these context records are authoritative for channel-specific resolution. XML availability does not enumerate XML's entire operation inventory again for each channel.

Unselected, shadowed, ambiguous and unused occurrences remain source inventory, subject to the existing keyed-format replacement policy. One canonical resource note can have multiple qualified consumers. Definition identities and source bytes are unchanged; manifest schema version is now 3 (identity version 1). Existing schema-two vaults remain readable by Excel. Converter readers do not opt into schema three and fail explicitly rather than treating shared dependencies as isolated operation views.

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

Do not replace a legacy run with scoped input. Reimporting identical scoped evidence is allowed; changed evidence requires a fresh run. Preserve original vault/database pairs for existing legacy resume. Source overwrites in old vaults can only be recovered by regeneration from the original source.

See the [migration plan](plans/composer_mapper_vault_hierarchy_migration_plan.md) for remaining converter stages and rollout gates.

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
