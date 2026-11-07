# Huge Bank Demo intake parity audit

Initial audit: 2026-11-06. Reporting fixes and comparison rerun: 2026-11-07.

**Result after reporting fixes:** all three reporting regressions are fixed. The
repeated Huge Bank Demo comparison passes for the audited selection, complete map,
shared-library decisions and workbook reporting. No open findings remain within
this audit's scope. Intentional schema/storage and AST improvements remain as
described below; this is not byte-for-byte equality of the two run folders.

## Baseline and method

- Old implementation: the actual `before-mapper-change` tag, commit
  `1d8909652e71a307cf0194788b3b612647c5f183`, extracted into an isolated directory.
- New implementation: `fbf2fb4` plus the local reporting fixes listed below, using
  a fresh selected intake against the unchanged indexed Huge Bank Demo map.
- Same original source folder, workspace ID `huge-bank-demo`, and JDK 25.0.3.
- Selected operation: `INTERNET/GetClientOverviewOpHuge00001`.
- Required operations: `INTERNET/GetClientLinksOpHuge00001` and
  `INTERNET/ValidateClientLinksOpHuge00001`.
- Both compared global maps cover INTERNET, IVR and XML. The old scoped schema-3
  mapper was rebuilt from its original sources; its converter and original Java
  scanner were executed from the isolated old checkout. The indexed map is schema 4.
- Comparisons use readonly original databases/maps. Library planning runs against
  private database copies. Generated audits and snapshots live under ignored
  `work/mapper-intake-parity-audit/`.

An initial old invocation used the old `legacy_components` configuration, which
passes a channel filter to the mapper. Its selected/global Java inventory matched,
but its 336-operation map was not an equivalent global-map baseline. A second old
run used the old `behavior_units` setting to disable that mapper filter, producing
the full 480-operation map. Both stop at `scoped_inventory_ready`, before conversion
strategies execute. No AI conversion, deployment or business operation was run.
This is a correctness audit, not a controlled performance benchmark.

## Exact matches

These comparisons checked complete records and identities, not just totals.

| Area | Compared quantity | Result |
|---|---:|---|
| Selected operation contexts | 3 | Exact match, including selection flags and ordered connections |
| Selected Java implementations | 22 | Exact identity, ownership, source path and source hash match |
| Selected configured definitions | 39 | Exact XML, selectors, hashes and implementation bindings |
| Selected configured uses | 97 | Exact references, multiplicity, provenance and resolution state |
| Selected Java dependency edges | 78 | Exact callers, targets, source offsets, kinds and names |
| Selected Java dependency-use records | 1,364 | Exact use identities and reference counts |
| Selected context bindings | 88 | Exact reference/step keys, definition identities and relative note paths |
| Selected imported source payloads | 38 | None missing; five have the AST improvements explained below |
| Global Java implementations | 513 | Exact source identity, package, root, ownership and hash facts |
| Global Java source dependency edges | 1,162 | Exact match against the original converter |
| Global original consumer/root groups | 5,760 | Exact roots, operation identities and multiplicities |
| Global selected-target factors | 571 | Exact counts |
| Global configured definition/operation counts | 18,960 | Exact match |
| Global implementation usage summaries for selected targets | 22 | Exact consumers, operation/channel counts, direct and indirect reference counts |
| Global configured usage summaries for selected definitions | 39 | Exact counts |
| Source/classpath diagnostics | 0 | Same empty diagnostics |
| JAR/JDK classpath report | Complete report | Exact match |

All 18 inventory comparison sections passed. Independently selected old records
were compared with the new selected records; the comparison did not merely look up
new IDs in the old output and overlook absent old selected records.

## Syntax and complete XML facts

The original `SourceReferenceScanner.java` was compiled from the old tag and run
over all 513 Java files. Its ordered facts were compared with the indexed database:

| Fact | Original count | Indexed result |
|---|---:|---|
| Reference sites | 33,954 | Exact match, including names, kinds and source offsets |
| Imports | 3,110 | Exact match, including static-import flags |
| Variable facts | 7,007 | Exact match |
| Method facts | 798 | Exact match |
| Type facts | 513 | Exact match |
| Package facts | 513 files | Exact match |

All 493 captured XML/INI/metadata documents were reconstructed from stored facts
and compared with the original XML reader's complete trees. Attributes, child
order, text, whitespace and serialized subtrees matched. Raw source hashes also
matched. This checks the stored source structure beyond the selected Markdown.

Declared project-reference relationships are identical. The indexed adapter sorts
the IVR reference list as INTERNET, XML, whereas the old list was XML, INTERNET.
Project visibility uses the same relationship set, and every resolved edge matches.
The original XML ordering remains in captured XML facts. No compiler classpath
precedence is inferred from that diagnostic list.

## Full mapper products

| Product | Old | Indexed | Result |
|---|---:|---:|---|
| Operations | 480 | 480 | Same entities and source identities |
| Operation steps | 2,688 | 2,688 | Same occurrences, including repeated IDs |
| Formats | 776 | 776 | Same entities |
| Contexts | 11 | 11 | Same entities |
| Java class notes | 513 | 513 | Same entities |
| Total canonical entity notes | 4,468 | 4,468 | No missing or extra entities |
| Execution contexts | 480 | 480 | Exact contextual records |
| Operation calls | 336 | 336 | Exact logical call graph |
| Call issues | 0 | 0 | Same |

Every entity's source identity, path, selector, source hash and other manifest
metadata matched. All qualified consumer lists matched their normalized SQL
representation. Both maps' physical note hashes were checked: no mismatches.

After normalizing the intentional schema-3/schema-4 frontmatter version change,
**4,463 of 4,468 note bodies match exactly**. The five differences are Java metadata
improvements, not missing source/configuration detail. All non-Java entity notes
match. The three channel notes also match exactly. The empty diagnostics index
changes to the new paginated-report pointer; both structured diagnostic sets are empty.

Expected representation differences were normalized explicitly: schema version,
the resulting physical note hash, absolute output folder prefixes, normalized
consumer storage, and run-specific generated library versions. Source hashes,
configuration XML, reference positions, multiplicities and business values were
not ignored.

## Five Java metadata improvements

All 513 original regex-parser Java models were compared field by field with the
persisted AST metadata. Packages, names, parents, interfaces, imports, return
codes/meanings, behavior classifications and external dependencies are unchanged.
No method or setter was removed.

| Class | AST difference |
|---|---|
| `AttributeXmlFormatDecoratorImpl` | Adds `formatXmlAttributes` |
| `CCOperationStep` | Adds `setContext` as method/setter; corrects its exception type |
| `DSEServerOperation` | Adds `setContext` as method/setter; corrects its exception type |
| `AbstractFormatElement` | Adds `addChild` and `unformat`; removes two malformed exception strings |
| `DemoXml` | Adds `elements` |

The old exception regex swallowed declarations after abstract methods, producing
values such as `Exception; ... public void setContext(Context context)`.
Four malformed strings across three classes disappear; proper `Exception` entries
are added or retained. Total improvement: six methods and two setters added.
The selected imported payloads retain these improved Markdown/parsed setter details.

## Shared-library decisions

Each version's own library planner was executed against copies of its run database,
with the same thresholds of five consumers for sharing and more than ten for the
broad library.

| Planning selection | Candidate components | Libraries | Comparison |
|---|---:|---:|---|
| Overview operation alone | 26 | 1 | Exact match |
| All three required operations | 28 | 1 | Exact match |

Assignments, consumers, distinct usage counts, raw reference counts, fingerprints,
conversion order, library dependencies, library build order and diagnostics all
match. Only generated per-run library version strings were normalized.

## Findings and fixes (2026-11-07)

### 1. Source-index report fields — restored

The initial [indexed report writer](../source/runtime/indexed_intake.py#L69) omitted
`workspace_root` and `class_projects` from `java_source_index.json`.
The old report contains both. The indexed map still holds the complete ownership
facts for all 513 implementations, and the conversion inventory matches; the loss
is in the inspection/report interface.

Fixed: the report includes `workspace_root` and SQL-backed `class_projects` for
selected files. The default global ownership lookup is unchanged; the report
projection does not recreate a global source dictionary.

### 2. Completed import task and summary — restored

The old run recorded a completed `LegacyComposerAnalysisAgent` task with its import
summary in `agent_tasks`. The initial indexed run recorded zero agent tasks.
The initial [indexed branch](../source/runtime/pipeline_runner.py#L75) bypassed the
existing agent completion writer and discarded the returned `VaultImportSummary`.
The shared completion writer now records that already computed summary.

Fixed: both intake paths use `record_import_summary` in the existing analysis
agent. Indexed intake supplies the summary returned by its completed import and
records one completed task. It does not repeat validation or import. Summary
counts describe the imported selected/required scope, rather than falsely claiming
that all global map notes were imported into the selected run.

### 3. Streaming Excel header styling — restored

The old portable exporter and new indexed exporter were run on their corresponding
complete maps. Every cell value matches in Migration Plan, Operations and
Relationships. Table ranges, row heights, column widths, freeze panes and data
number formats match.

Initial header cells lost their bold white font, dark fill and horizontal centering:
`A5:F5` on the first two sheets and `A5:D5` on Relationships. The cause is the
[header append call](../source/tools/operation_call_tools/streamed_workbook.py#L31),
which previously omitted `header=True`. The flag is restored and the portable
Excel snapshot has been regenerated. No workbook data or relationship rows are
changed.

## Scope and evidence

This audit checks source/configuration, dependency, sharing and reporting detail
for this fixture and selection. It does not prove every possible enterprise
workspace, language form or dynamic runtime dependency. The initial audit was
read-only; the follow-up changes only the three reported regressions. No pushes,
deployment or model conversion were performed.

Follow-up changed files and reasons:

| File | Purpose |
|---|---|
| `source/runtime/indexed_intake.py` | Restore report fields and persist the existing selected-import summary |
| `source/tools/component_inventory_tools/mapped_inventory.py` | Add a lazy selected-file ownership projection without changing default lookup behavior |
| `source/agents/legacy_composer_analysis/agent.py` | Share the existing completed-task writer across intake paths |
| `source/tools/operation_call_tools/streamed_workbook.py` | Restore header styles |
| `Excel Generator.py` | Regenerate the portable copy of the same writer |
| `source/tests/test_indexed_startup.py` | Check restored fields/task and forbid duplicate legacy import |
| `source/tests/test_indexed_map_export.py` | Check header formatting against the existing workbook writer |
| This report | Record fixes and repeat-comparison evidence |

Java parsing/resolution, dependency multiplicities, conversion gates, legacy input
formats and unrelated code remain unchanged. Existing unrelated POM edits and the
architecture diagram were left untouched.

Local evidence under `work/mapper-intake-parity-audit/` includes:

- `inventory-summary.json` and `inventory-comparison.sqlite`;
- `syntax-facts-summary.json`, `xml-facts-summary.json`;
- `map-summary.json`, `map-comparison.sqlite`, `control-notes-summary.json`;
- `java-metadata-summary.json`, `java-metadata-differences.jsonl`;
- `library-plan-summary.json` and both normalized planner snapshots;
- `workbook-summary.json`, `workbook-style-differences.json`, `old.xlsx`, `new.xlsx`;
- `report-and-state-summary.json`, old source snapshot, rebuilt old mapper and run logs.

## Follow-up verification (2026-11-07)

Fresh intake: `work/mapper-intake-parity-audit/fixed-runs/fixed-reused-overview`.
It reached `scoped_inventory_ready` using the existing map, with three operation
contexts and 22 selected Java implementations. The mapper was not rerun.

- All 18 selected/global inventory comparison sections pass against the original
  converter baseline. Both library-planning selections match in every compared
  field, including usage counts, consumers, fingerprints and build order.
- The complete map recheck matches all 4,468 entity metadata records and consumer
  lists, 480 execution contexts, diagnostics and the 336-call graph. No physical
  note hash fails. The same five documented Java metadata improvements are the
  only normalized Markdown differences; all 38 selected source payloads are present.
- `java_source_index.json` restores `workspace_root` and exactly the 22 selected
  file-to-project ownership records, matching the independently selected old data.
- One completed import task is recorded. Its summary matches the actual imported
  scope: three operations, seven operation steps, three formats, three contexts and
  22 Java classes, with no errors or unresolved references. Recording the task
  does not repeat import, validation or Java parsing.
- The regenerated portable export matches the old workbook in all three sheets:
  values, populated-cell fonts/fills/alignment/number formats, dimensions, row
  heights, column widths, freeze panes and tables.
- Focused validation: 27 tests passed across indexed startup, indexed export,
  legacy import-agent behavior and scoped startup. Both indexed startup variants
  were then rerun with an explicit guard against duplicate legacy import: two
  passed. Only existing dependency deprecation warnings were emitted.

Additional evidence: `fixed-run.json`, `reporting-fixes-summary.json` and
`audit-result.json`. The comparison summaries above were refreshed against this
fresh intake. Original pre-fix summaries are preserved in
`work/mapper-intake-parity-audit/before-reporting-fixes/`.
