# Composer Mapper

This version is designed for large Composer/WSBCC repos.

Flow:
1. Discover XML / INI / Java files
2. Build lightweight indexes only
3. Parse one source file at a time
4. Write markdown immediately
5. Discard parsed objects and move on

Output:
- operations/
- opsteps/
- formats/
- contexts/
- classes/<package path>/
- analysis/unresolved-references.md

## Scoped vaults and repeated operation-step IDs

Use `--vault-layout scoped --workspace-id "your-workspace-name"` for the channel/operation hierarchy and manifest. Legacy layout remains the default. Scoped output requires an empty or new destination outside the source tree. See the [scoped vault guide](../../docs/scoped_vaults.md).

Every non-XML channel has XML as its implicit base, without requiring an XML import in `dse.ini`. Include XML's configuration and sources in the input workspace, including when mapping a single channel. XML defaults are applied first, declared imports retain their order, and local definitions take precedence. Schema-three scoped output writes each source definition once, follows referenced inherited operations transitively, and records consuming-channel connections in `operation_contexts`. XML availability never expands every channel into the complete XML operation inventory. Local overrides and `onlyFor` apply to the connections. Both Excel generators support this layout; converter support remains gated. Regenerate a fresh vault to adopt it.

```powershell
java -jar target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\code\composer-projects" --vault "C:\docs\new-composer-vault" --vault-layout scoped --workspace-id "enterprise-composer" --md true
```

An opStep ID is a readable label, not a unique source-occurrence key. Scoped generation preserves repeated IDs within one operation, including repeated IDs applicable to the same channel. Canonical notes retain all source steps; contextual connections select `onlyFor` steps for the consuming channel and preserve their source order. Original IDs, implementations, parameters, and transitions remain unchanged.

Step labels whose generated filenames are unique retain `opsteps/<label>.md`. Repeated labels, including capitalization variants, use readable occurrence folders, for example `opsteps/occurrences/2/Check.md` and `opsteps/occurrences/5/Check.md`; folder numbers are one-based source positions. Canonical note `step_index` values are zero-based source positions. Context entries expose effective ordered `step_notes`, `entry_step_note` and resolved `transition_targets`; their list order determines effective positions. Source selectors retain each occurrence's identity independently of its label. Unused source occurrences remain in resource inventory, with occurrence folders where needed to prevent overwrites.

Duplicate grouping compares generated step filenames without case sensitivity. For example, `SetSITE` and `SetSite` belong to the same duplicate group and both receive occurrence folders; their labels, spelling, implementations, parameters, and order remain intact. This avoids Windows treating two notes as one file. Grouping does not merge source occurrences or change Composer's case-sensitive named-transition lookup. The same grouping applies to inventory steps. Before rendering an operation, all its entity-note destinations are reserved; inventory destinations are reserved before each write. Any remaining path conflict is reported with both source paths/selectors before the conflicting note can overwrite another. The manifest retains its final duplicate-path check. This is per-operation/per-inventory-note validation, not a promise that every possible conflict is found before the entire run starts.

Routing follows the verified Composer lookup: `next` advances one position, `end` terminates, and a named target searches from the current position inclusively, then wraps to the beginning. Named labels match exactly. This supports repeated labels, self-jumps, and backward jumps. A missing named target is shown as unresolved; the runtime lookup returns `-1`. Diagrams and step-note links distinguish occurrences rather than collapsing equal labels. Legacy generation is unchanged.

## Operation names containing hash characters

Names such as `#GPKOp` keep their original IDs and physical filenames. Markdown link destinations encode `#` as `%23` and literal `%` as `%25`; labels and manifest filesystem paths stay unchanged. Obsidian output uses standard Markdown links for paths containing `#` or `%`, retaining wiki syntax for ordinary paths. Both Excel generators distinguish encoded filename characters from heading fragments and decode link paths once. See [link compatibility and regeneration](../../docs/scoped_vaults.md#hash-characters-and-link-destinations). Regenerate into a fresh vault to update old Markdown links; no source renaming is required.

## Scoped run progress and timing

Scoped runs print timestamped phase and channel boundaries, plus the first operation in each channel. A console heartbeat every five seconds shows the current phase or operation and elapsed wall time, including while a single operation is still being rendered. Operation events include the channel/name, overall operation number/total, channel-local number/total, and remaining count. Totals count declared operation roots, not the whole inherited inventory. Referenced inherited contexts are logged separately as resolving connections and share canonical source notes. Ambiguous operation selections are recorded as skipped rather than completed.

Every operation start and completion is flushed to `<vault>/composer-mapper.log`. The UTF-8 log also records indexing progress, unused inventory, manifest finalization, and a success or failure summary. Log timestamps use the executing computer's local time and offset. Periodic console heartbeats are console-only; persistent events are written at phase boundaries, for each operation, and periodically during indexing/inventory/finalization.

The final successful summary reports channels, completed/skipped operation views, entity-note count, inventory-note count, diagnostics, and elapsed `HH:MM:SS`. For command-line runs, elapsed time includes source discovery. The initial discovery message is console-only because the new vault has not yet been validated and created. Entity-note totals exclude the log, channel summaries, and other control files; they are not a predicted final filesystem file count. Inventory and finalization can continue after all operation views are written. Progress reporting does not estimate completion time or change conversion behavior.

Existing destination validation remains in force: a scoped run requires an empty or new vault and never clears an existing one. An in-progress enterprise process cannot acquire this logging update; rebuild and use it on a subsequent run. Legacy output and logging behavior are unchanged.

## Minimum install requirements

- JDK 25 (set JAVA_HOME and PATH to the same JDK for Maven and Java)
- Apache Maven 3.8 or newer
- Access to Maven Central on the first build, so Maven can download build plugins
- An IBM Composer code base containing XML, INI, and/or Java files
- A writable output folder for the generated documentation tree

Check local versions:

```bash
java -version
mvn -version
```

## Compile the project

From the project root:

```bash
cd source/composer-mapper
mvn clean package
```

This compiles the Java sources and creates the runnable jar:

```text
target/composer-mapper-1.1.1-jar-with-dependencies.jar
```

## Run tests

From the project root:

```bash
mvn test
```

The current project has no test sources yet, but this command still verifies that the project compiles successfully through Maven's test lifecycle.

## Generate a document tree with standard Markdown links

Use this mode when the generated documentation will be viewed in a regular Markdown renderer, Git repository browser, static site generator, or any tool that expects links like `[GetClientLinksOp](operations/GetClientLinksOp.md)`.

```bash
java -jar target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\code\ibm-composer" --vault "C:\docs\composer-map" --md
```

Arguments:
- `--root` points to the IBM Composer code base to scan.
- `--vault` points to the output folder where the generated Markdown document tree will be written.
- `--md` switches generated cross-references from Obsidian wiki links to standard Markdown links.

The output folder will contain the generated document tree:
- `operations/`
- `opsteps/`
- `formats/`
- `contexts/`
- `classes/`
- `analysis/unresolved-references.md`

## Generate an Obsidian vault with wiki links

Use this mode when the generated documentation will be opened directly as an Obsidian vault. This is the default behavior and produces links like `[[operations/GetClientLinksOp|GetClientLinksOp]]`.

```bash
java -jar target/composer-mapper-1.1.1-jar-with-dependencies.jar --root "C:\code\ibm-composer" --vault "C:\obsidian\vaults\composer-map"
```

Arguments:
- `--root` points to the IBM Composer code base to scan.
- `--vault` points to the Obsidian vault folder where the generated notes will be written.
- Omit `--md` to keep the default Obsidian wiki-link format.
