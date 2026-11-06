# Composer Mapper AST and Segmented Intake Plan

Status: implemented as an opt-in path and acceptance-tested, 2026-11-06.
See [implementation, configuration and validation notes](../composer_analysis_store.md).
Stable generation defaults and conversion gates remain in place; default promotion
requires the release gates below.

## 1. Objective and boundaries

Make the Composer map the reusable source of XML configuration facts, Java syntax
facts, and static Java dependency relationships. Generate it with bounded memory,
then let the converter query only the selected operations and their dependency
closure without repeating whole-project source parsing.

The Composer Mapper remains a standalone, global mapping tool. It accepts a source
workspace and maps that workspace independently of a converter configuration. Do
not make it map only the converter's selected operation. Existing explicit channel
filters remain supported with their existing semantics and declared coverage.

There are four separate activities:

1. Discover and fingerprint source files and project metadata.
2. Parse each changed Java/XML/INI source revision once into reusable facts.
3. Resolve those facts into qualified definitions, references, execution contexts
   and global static dependencies, using disk-backed indexes.
4. Select and load the converter's reachable subset, retaining accurate global
   sharing information without hydrating unrelated code or note bodies.

The first complete map still requires global analysis. Moving that analysis into
the mapper does not magically remove its first-run cost. Savings come from removing
repeated mapper parsing, eliminating duplicate converter analysis, reusing an
unchanged map across runs, and updating only affected facts/resolution on changes.

This is not a compiler/runtime call-graph replacement. Preserve the converter's
current static dependency semantics, declared project visibility, ambiguity
diagnostics and cycle rules. Reflection, dynamic service lookup and runtime
dispatch must not become invented, supposedly proven edges.

## 2. Audited code and actual products

The design below follows inspection of the mapper source, its README, converter
readers, existing regression tests, and generated huge-bank-demo map products.
It is not based only on names such as "StreamingGenerationService".

| Area | Verified behavior / risk | Required response |
|---|---|---|
| Java source discovery | `JavaClassIndexer` reads source using regex; `JavaClassParser` reads it again for metadata. Scoped generation invokes that parser during import traversal and rendering. | One canonical AST analysis supplies declaration indexing, metadata and reference facts. |
| Java metadata | The parser records package/class names, imports, parent/interfaces, methods/setters, thrown exceptions, return codes/Javadoc meanings, behavior categories and inferred external dependencies. | An AST reference scanner alone is insufficient; preserve every existing metadata field too. |
| Java relationships | Scoped generation follows non-wildcard explicit imports; class Markdown contains imports and inheritance strings, not a complete static source dependency graph. | Persist actual reference sites and qualified resolved edges, separately from documentary import lists. |
| Concrete missing edge | `FormatDecoratorHolder.initializeFrom(Tag tag)` uses a same-package type. Its generated Markdown has `Imports: None` and no `Tag` dependency; the converter graph contains `FormatDecoratorHolder -> Tag`. | Mandatory differential regression for the shared scanner and persisted map. |
| XML parsing | Legacy index/render passes parse XML separately. `ScopedDefinitionCatalog` retains `Element`-backed identities and therefore live DOMs across the workspace. | Persist parse facts; retain neither every DOM nor every parsed operation tree. |
| INI and inheritance | `dse.ini` is XML; import resolution/registration currently revisits it for channel chains. | Parse it once into ordered registration/import facts; evaluate consuming contexts from those facts. |
| Source hashing | `FileUtil.sha256()` uses `readAllBytes`; writers repeatedly hash the same source. `SourceDefinitionIdentity` also derives revision evidence. | Stream hashes from captured bytes once per analysis revision and pass digests to consumers. |
| Manifest writing | `VaultManifestWriter` retains all entries, path reservations, operation contexts and consumer sets; it rereads and rewrites notes during metadata finalization. | Store records/joins on disk and render each final note from finalized metadata. |
| Converter manifest reading | `iter_manifest_fields` streams `entities`/`diagnostics`, but other fields such as `operation_contexts` can be decoded as one value. `read_vault_manifest` can then retain the full inventory. | Token streaming is not enough: remove downstream whole-project retention and giant nested values. |
| Converter import | Shared import constructs `by_note`, context lists and membership sets and reads note bodies after validation. Legacy source-artifact upserts commit per artifact. | Indexed lookups, bounded transactions and a single validated import boundary. |
| Existing converter cache | Syntax is already content-verified, but full source discovery and inventory still precede mapper generation in `pipeline_runner`. | Resolve/generate the map first on the new path; reuse its facts instead of running those stages twice. |
| Existing selected counts | The converter already stores compact consumer/root and root/target factors, selected detail, and disk-backed traversal. | Reuse these semantics; do not restore global operation-times-reference expansion. |

Measured context: the 1,012-file fixture has 480 operation XML files and 513 Java
files. The selected overview operation required three operations and 22 Java
implementations. The scoped comparison took 38.4 seconds for inventory processing,
11.7 seconds for reports, 203.1 seconds for mapping and 16.1 seconds for subsequent
validation/import to `scoped_inventory_ready`. These are measurements, not future
performance promises. The default legacy-layout run emitted 1,393 collision warnings
and stopped at dependency preflight; do not treat that run as a valid semantic oracle.
The local measurement artifact is `work/huge-bank-demo-timing-20261106-0112.json`.

## 3. Non-negotiable scale requirements

- No complete-project AST collection, DOM collection, dependency dictionary,
  manifest object, `operation_contexts` array or consumer list in application memory.
- No `readAllBytes`/`read_text` followed by whole-project JSON decoding. No
  stream-then-`list()`/`fetchall()` implementation hiding the same allocation later.
- No global transitive-closure matrix and no persisted operation-by-reference-site
  Cartesian product. Work for a highly shared class must not multiply its full
  source, Markdown or reference-site records by its number of consumers.
- Bound batches by bytes as well as item count. Bound queues, SQL caches,
  diagnostic buffers, Markdown rendering buffers and worker concurrency explicitly.
- A selected closure may itself be huge or equal to the workspace. The same paging
  and disk-backed traversal must apply; selection is not a memory guarantee.
- Disk-backed collections must have indexed query APIs. Replacing a dictionary
  with one unindexed query per node can remain prohibitively slow.
- Do not weaken provenance, validation, dependency blockers, source occurrence
  identity, conversion gates or global usage correctness to meet a timing target.
- Keep parsing and source resolution separate. Unused imports are documentation,
  not evidence that one class actually uses another.

## 4. Parse-once contract

### Java

Use one shared implementation derived from the existing
`SourceReferenceScanner.java` and its converter resolution policy. Its current
visitor extracts reference facts but does not yet supply all mapper metadata.
Add metadata extraction to the same compilation-unit analysis rather than merely
calling that scanner alongside the old Java regex parser in production.

For one immutable source revision:

1. Open the source and stream raw bytes into a bounded snapshot/spool while hashing.
2. Decode from that captured content, preserving UTF-8 and Windows-1255 fallback
   behavior, warnings, raw-byte hashes, BOM policy and source-offset conventions.
   Encoding fallback must not reopen the original source just to try another decoder.
3. Feed the captured text to one `JavacTask` parse with annotation processing off.
4. Extract declarations, imports, mapper metadata and reference sites in that
   analysis session; flush normalized records incrementally.
5. Commit complete file facts, release the compilation unit and close the bounded
   compiler batch. No AST survives into map rendering or converter runs.

Reference coverage must match the existing scanner: declared/parameter/return
types, inheritance, generic bounds, annotations, construction, casts, arrays,
instance checks, static references/imports, qualified names and method-reference
qualifiers. Include same-package/wildcard resolution and nested/top-level type
identity. Ignore comments/string literals as dependencies and retain the existing
empty/comment-only source policy. Treat `package-info.java`, `module-info.java`,
interfaces, enums, records and annotation declarations explicitly rather than
confusing "no ordinary class" with a failed file.

Keep the old import list and documentary source-candidate relationships available.
Do not silently replace them with actual-use edges: they answer different questions.
Keep interface/parent metadata distinct from proof of runtime class loading.

Full method dispatch, overload binding or reflection analysis would be a separate
capability. Do not enable compiler-wide attribution that loads the entire workspace
or executes annotation processors to obtain the existing class-level usage graph.

### XML and INI

Preserve the current Composer XML rules and parser security settings. The change
is reusable parse facts and storage, not a new interpretation of Composer.

Perform one secure streaming XML parse per changed file, including `dse.ini`,
`.project`, `.classpath` and any supported XML build metadata under the relevant
metadata policy. Disable external entity/DTD/schema access, entity expansion and
XInclude as today; do not introduce network resolution.

Preserve XML-declaration/BOM encoding detection, current namespace/tag matching,
text/CDATA handling, comments/whitespace policy and safe DOCTYPE behavior. Do not
blindly decode every XML snapshot as UTF-8 or silently change namespace awareness
when replacing DOM traversal with a streaming parser. Add these to parity fixtures.

Persist ordered elements, attributes, text, selectors, definition ownership,
raw occurrences and channel registration/import declarations into normalized rows.
Maintain a bounded ancestor stack and disk-backed sibling/key tracking. Effective
keyed-child selection may only be known after later siblings are seen; record
occurrences first and resolve the existing last-declaration policy afterward.

Do not cache whole DOMs. Adapt existing business extraction/resolution rules to
ordered row/subtree cursors. A bounded DOM adapter for small fragments can ease
migration, but must not reparse source XML and must reject/spill oversized fragments.
Large single XML files and operations with thousands of children require the
cursor path, not an unconditional per-file DOM or per-operation list.

Different consuming channels can legitimately require different effective views
of one parsed definition. Re-evaluating such a view is not reparsing the source.
Cache/reuse completed effective results by definition plus resolution-context key.

### What "once" does and does not promise

The guarantee is one successful source parse for a content hash and parser-policy
version, with zero parses on a verified cache hit. Failed/incomplete attempts are
not reusable successes. Crash recovery can repeat an uncommitted batch.

Freshness checks may reread bytes for hashing; they must not repeat AST/XML parsing.
Do not promise literally one lifetime physical read while also requiring reliable
change detection. Raw content hashes, decoded offsets and selected-file byte checks
remain independently verifiable. Do not change source encoding or rewrite sources.

## 5. Shared analyzer and standalone packaging

Create a focused Java analysis core with a callable API and a small command-line
adapter. The mapper calls it in-process or through bounded workers; the converter's
old-map compatibility scanner uses the same implementation. Do not maintain two
copied visitors or two divergent reference-resolution policies.

Extract source-name/project-visibility resolution into the shared core as well.
Use a bounded type-lookup/provider interface over persisted indexes. The mapper's
resolver service becomes an adapter; the Python compatibility path invokes the
same resolver in batches through the shared CLI, not a JVM per reference. Retain
the existing Python resolver as a differential oracle only during migration, then
as a compatibility adapter where its API is still used. Moving only the visitor
while maintaining independent Java/Python resolvers would risk different counts.

Use a small Maven reactor for the shared core and mapper. Preserve the standalone
fat-JAR launch contract: installed mapper users must not need Python, the converter
checkout, an AI model, Maven or online access at mapping time. Package the analysis
classes and the storage JDBC driver in the distribution. Build dependencies must
be pinned, available through the permitted Maven/Artifactory route and tested with
offline Maven caches. Document the shared-module build/install step and update the
existing CMD wrapper; do not leave the previous documented build command silently
broken by an unpublished sibling artifact.

The shared core should support the converter's JDK 21/25 scanner paths as required
by existing tests; the mapper's current JDK 25 requirement remains explicit. Record
the producer JDK, source language level, analyzer version and resolver policy. A
map produced under incompatible settings is not a cache hit. Keep the existing
scanner entry point as a thin compatibility adapter, not a duplicate implementation.

A project-aware resolution context is required before resolving raw facts. Read
declared source roots, test exclusions and project/classpath relationships from
the workspace using the current converter rules. Duplicate FQCNs remain separate
source candidates identified by workspace/project/path; channel inheritance alone
is not a Java classpath. Preserve unresolved and ambiguous candidates and diagnostics.

If converter-supplied visibility/classpath overrides differ from the map's context,
require a matching revision or re-resolve affected persisted facts into a new
qualified resolution revision. Do not ignore the override, reuse incompatible
edges, or launch another whole-source parse just to resolve stored syntax facts.

## 6. Persistence: Markdown plus a normalized, versioned analysis store

Keep Markdown as the readable map product. Add an indexed SQLite analysis artifact
for machine queries. Do not force the converter to reconstruct the graph by opening
every Markdown note. Do not put the whole project graph in one JSON document.

Proposed scalable layout:

```text
<vault>/
  vault-manifest.json             # small schema-4 descriptor, no entity arrays
  analysis/<revision>/analysis.sqlite
  channels/...                   # existing readable canonical-note hierarchy
  analysis/...                   # diagnostics and paginated human reports
  composer-mapper.log
```

The descriptor contains schema/identity versions, workspace/revision IDs, producer
and policy fingerprints, coverage, completion/quality flags, database path/digest,
row counts and publication state. It stays bounded (target <=64 KiB), and contains
no file list, consumers array, operation-context array or adjacency map.

Suggested normalized relations, all scoped to an immutable revision:

| Relations | Stored facts and essential indexes |
|---|---|
| `files`, `file_analysis` | Project-relative identity, source-root ownership, content hash, encoding, language, parse status/version. Index path, project, hash/policy. |
| `java_types`, `java_members`, `java_imports` | Qualified declarations, ordered methods/setters/return-code facts, parent/interfaces, raw import facts. Index type name/project and file/ordinal. |
| `java_reference_sites`, `java_edges`, `java_candidates` | Caller, source offset/ordinal, kind/name, target, resolution status and candidates. Index outgoing caller, incoming target, file, unresolved lookup name/project. |
| `xml_nodes`, `xml_attributes`, `definitions` | Ordered structural facts, selectors, raw attributes, owner scope, kind/name and effective/shadowed status. Index parent/ordinal, owner, kind/name/channel. |
| `channel_imports`, `tag_mappings`, `execution_contexts` | Declared import order, effective bindings and consuming-channel operation identities. Index channel, source definition and operation identity. |
| `step_occurrences`, `transitions`, `operation_calls`, `context_bindings` | Canonical and effective step order, exact targets, nested calls and reference bindings. Index context/ordinal, caller and callee. |
| `configured_uses`, `consumer_roots` | Global operation-origin identities, channel/context identity, implementation/definition roots, occurrence multiplicity. Index root and consumer. |
| `notes`, `note_pages`, `diagnostics`, `revisions` | Stable paths/hashes, ordered continuation pages, bounded diagnostic records, completeness and validation receipts. Use disk uniqueness constraints for collision checks. |

Do not store a hidden giant `record_json` per operation, file or manifest. Child
collections are child rows. Small scalar record JSON is permitted with a byte cap;
large text/Javadoc/XML fragments are streamed blobs or chunk rows. Preserve original
text where current products require it, not serialized live AST/DOM objects.

Keep Java reference sites distinct from grouped caller/target edges. Reference
multiplicity, diamond paths, repeated configured uses and distinct consumer counts
are different quantities. Store large integer counts as decimal values with safe
arithmetic where SQLite integers could overflow; never silently cap them.

### Publication, recovery and validation

- Use a private builder store; commit bounded file/batch transactions. A complete
  file-analysis marker is written only after its facts commit successfully.
- Update metadata/relationships in a new revision. An active converter sees only
  its pinned immutable revision, never a partially updated live mapper database.
- Checkpoint WAL, close writers and publish a self-contained database; do not
  distribute an analysis file dependent on unshipped `-wal`/`-shm` files.
- Hash/validate with bounded reads, then atomically publish the descriptor on the
  same filesystem. Account for Windows open handles and interrupted publication.
- Fail closed on missing/truncated artifacts, unsafe paths, inconsistent IDs,
  incomplete source analysis or unsupported capability versions. Keep full paths,
  file positions and original diagnostics. A documentation-only result with
  incomplete Java analysis must not advertise globally complete dependency data.
- Import in bounded transactions into revision-keyed staging/selected overlays.
  Publish readiness last. On failure, inactive staged rows may exist on disk but
  no caller can access them as a ready run. This replaces dependence on one giant
  transaction without weakening all-or-nothing visibility.
- Keep one validated receipt per immutable generation. Do not revalidate every
  note after each config prompt or again during the same import. Mutable/changed
  input invalidates the receipt; readonly flags alone are not an integrity proof.
- Resume pins the exact map revision and source policy. It does not silently
  switch to the newest map. Retain revisions referenced by active/saved runs.

## 7. Rendering and existing map products

Finalize global facts/counts in the store before rendering final note metadata.
Render notes with a bounded writer, hashing as bytes are written; stop rereading
and rewriting every note to insert metadata or recompute shared flags.

Keep canonical source notes separate from consuming execution contexts as today.
Do not create another full note for every operation that uses the same helper.
Preserve note root paths, headings, identities and links for existing definitions
where schema compatibility permits. Add direct Java dependency/reverse-reference
sections; do not print a transitive closure into every class note.

Preserve the documented meaning of existing `shared` and `used_by_steps` fields.
New transitive/global operation counts are explicitly named additional evidence,
not a silent reinterpretation of the old direct-step metadata. Any deliberate
change to an existing flag requires an approved contract/version change and tests.

For a huge individual note or a class used by thousands of operations, stream
continuation pages and link them from the root note. No silent truncation: expose
counts and explicit pagination/completeness metadata. Do not write an empty
`used_by_steps` list to mean "too large to display". New readers must follow the
paged contract; old-format compatibility exports retain their documented fields.

Both Excel export paths must read the indexed/paged format and retain their current
workbook semantics. The copied standalone `Excel Generator.py` must remain usable
outside this repository using its documented dependencies. Prefer standard-library
SQLite readers and a deterministic bundling process; do not hand-fork shared parsing
logic into an untested embedded copy. Export operation/relationship rows incrementally.

### Mandatory preservation matrix

| Existing ability / product | Preservation and regression gate |
|---|---|
| Discovery and invocation | Root/XML/INI/Java discovery, implicit XML availability, source-channel assignment, explicit channel filter, CLI flags, standalone JAR and documented build/run commands. No dependency on converter configuration. |
| Legacy output | Existing layout, clean/output behavior, collision diagnostics and Markdown/Obsidian modes remain a supported compatibility path. Do not silently reinterpret existing legacy maps as qualified maps. |
| Qualified identity | Workspace-relative provenance, project copies, selectors, original labels, usage IDs, canonical definitions versus consuming contexts, stable path reservation and duplicate checks. Any necessary identity-version change needs explicit migration tests. |
| Channel resolution | Implicit XML base without forced imports, declared import ordering, local overrides, transitive inherited operation calls, ambiguity handling, unused/shadowed inventory and no multiplication of every XML operation into every channel. |
| INI evidence | Tag mappings for formats/steps/operations/services, operation registry and service registry, provenance and current malformed-INI/required-channel diagnostics. |
| Operation Markdown | Context, ordered steps, `onlyFor`, Java dependencies, format roles/inline formats, raw operation attributes, host key, initial values, shared-component evidence and Mermaid flow. |
| Step occurrences | Repeated IDs within one operation, case-variant filenames, one-based occurrence folders versus zero-based source indices, canonical excluded steps and effective consuming-channel order. Never deduplicate by step label. |
| Transitions/calls | `next`/`end`, exact named-target matching, inclusive forward search then wrap, self/backward jumps, unresolved targets, return-body switches, nested operation calls and channel-aware call targets. |
| Format semantics | Nested definitions, keyed last-declaration wins, indexed repeats/order, exact indexed-wrapper allowlist, decorator attachment to the retained child, references not treated as new collection keys, source-relative selectors. |
| Format Markdown | XML structure, raw attributes, referenced tags, mapped Java candidates, inferred external dependencies, serialization notes and database lookup details (`fromTable`, `fromColumn`, `keyValue`). Preserve decorator order and field paths. |
| Context Markdown | Parent, type, raw attributes, channel defaults/overrides and resource-origin identity. |
| Java Markdown | Package/name, parent/interfaces, complete declared imports, method/setter names and ordering, thrown exceptions, numeric/named return codes and meanings, behavior categories, IBM/WAS warnings and database/API dependency hints. |
| Encodings and hashing | UTF-8/Windows-1255 behavior, BOM handling, original source bytes/hashes and offsets; no rewriting source to obtain a parse. |
| Links/consumers | Standard Markdown and Obsidian syntax, literal `#`/`%` filenames with single decoding, readable labels, source selectors, both Excel exporters and standalone-copy parity. |
| Diagnostics and output safety | Full XML error path/position, unresolved references, identity collisions before overwrite, incomplete-generation marker, no complete publication after parse failure, fresh scoped destination and source/output separation. |
| Progress | Phase/channel boundaries, first operation, periodic console heartbeat during long work, durable operation start/completion events, unused inventory and finalization progress, actual skipped/completed totals and elapsed time including discovery. |
| Conversion protection | Existing classpath uncertainty, source-change checks, cycle/ambiguity blockers, gate policies, dependency-first scheduling, current library thresholds, qualified intake boundary and refusal to silently combine incompatible evidence. |

Do not assume AST output automatically preserves regex-derived metadata. Establish
the baseline field-by-field. Run shadow comparisons only in tests/explicit evaluation
mode against the same captured source; do not ship permanent double analysis.
Classify every difference as preserved data, additive evidence, an intentionally
approved correction, or a regression. An unexplained metadata loss blocks rollout.

## 8. Converter fast path and execution order

For a new indexed map, intake becomes:

1. Validate config, source/output separation, toolchain and mapper capabilities.
2. Reuse a compatible completed map, or run global map generation once. Do not first
   invoke converter-wide regex discovery, AST parsing and XML inventory as today.
3. Open/attach the verified immutable analysis store read-only. Bind revision and
   resolver policy to the run, retaining the required source/classpath checks.
4. Select requested channel-qualified execution contexts using current include/
   exclude semantics. Follow operation calls and required callee contexts; preserve
   reporting/blocking of missing or explicitly excluded requirements.
5. Seed Java traversal with configured step implementations, format/decorator
   implementations and other current required bindings—not just obvious OP-step
   classes. Traverse persisted outgoing edges with a disk work queue and visited table.
6. Page only reachable definition records, note bodies and reference-site details
   into run-local overlays/evidence. Do not copy the entire global map into each
   run or load its operation graph merely to filter it afterward.
7. Query global consumers for the selected targets using the global store, produce
   bounded reports, and continue through the same intake/planning/gate boundaries.

"Only selected dependencies" means only those detailed records/bodies/ASTs are
hydrated. Compact global queries and streamed integrity checks remain legitimate
and necessary; do not claim that no unrelated index row is ever read.

The new fast path runs **zero full-workspace Java syntax parses** and **zero source
XML parses** when valid map facts already exist. Later conversion/compilation may
read or parse selected sources under its existing policy; that is not repeated
global intake. Avoid reparsing even the selected closure during intake if persisted
facts already answer the request.

Existing list-returning APIs can remain compatibility wrappers for bounded callers.
The large-project path must call iterator/query APIs throughout. Audit downstream
`ScopedVaultAccess`, operation-call discovery, scoped preparation, units and evidence
loading so one call cannot pull the full manifest/operation context into memory.

## 9. Exact global sharing without global detail expansion

Persist global operation-to-implementation/definition roots and raw Java edges once.
For the selected closure, use incoming-edge queries to find relevant global roots,
then compute the needed counts with disk-backed work tables and bounded arithmetic.
Do not traverse every unrelated root when indexed reverse reachability excludes it.

Reuse current factorization: root/consumer occurrence weights and root/selected-target
reference multiplicities. Compute summaries on demand and cache them by map revision,
counting-policy version and target. Do not persist every root-to-every-target pair
unconditionally; that can be quadratic. Delete/reuse per-root traversal scratch rows
and bound summary-cache disk retention.

Keep these quantities separate and test them independently:

- Configured occurrence count and direct references.
- Static reference-site multiplicity and indirect path multiplicity.
- Distinct original operation identities and distinct consuming channels.
- Source definitions versus imported/aliased execution contexts.

Consumers outside the selected conversion scope still contribute to the selected
components' global sharing counts. They need compact identity rows, not loaded
source or Markdown. Cycles use the existing diagnosed/counting policy; do not
introduce infinite path counting. Prefer disk traversal, with any small-graph
optimization capped by an explicit byte estimate and tested fallback.

Counts are exact relative to the declared source inventory and existing static
resolution policy. Propagate unresolved/ambiguous evidence and count-quality limits;
never turn incomplete evidence into zero consumers or claim runtime-dispatch proof.
Preserve current library ownership thresholds and assignments on equivalent evidence.

## 10. Incremental updates and freshness

Identify file facts by raw content hash plus encoding/parser/source-level policy.
Identify resolved edges additionally by project visibility/classpath and symbol-index
revision. Identify effective XML views by definition and channel/import/override
policy revision. Reusing syntax does not imply reusing stale resolution.

- Unchanged content: reuse facts and notes; no AST/XML parse.
- Changed file: parse once, replace that file's fact rows in the builder revision,
  and re-resolve affected callers/bindings using indexed symbol-use queries.
- Added/deleted/renamed types: remove stale declarations/edges; re-resolve possible
  incoming references, including previous unresolved names and wildcard imports.
- Changed project visibility or Java policy: re-resolve the affected scope; only
  reparse if syntax policy requires it. A broad resolution update can be necessary.
- Changed INI/overrides: recompute affected effective contexts and consumers from
  stored XML facts, without reparsing unrelated XML/Java.
- Source changes during analysis/publication: reject the mixed result and identify
  the changed files. Retain reusable completed file facts, not a ready mixed graph.

A normal mutable checkout may still require a streamed global source-file inventory
and content-hash check to claim globally current sharing counts. Filesystem watchers,
size and mtime are hints, not definitive freshness proof. A trusted immutable source
snapshot/revision can provide stronger reuse. Explain this residual I/O cost honestly.

Use a writer lock and immutable revisions; never run two writers against a published
map. Interrupted runs resume only compatible completed batches. Recovery does not
delete/rearrange the user's old map, corrupt active readers or publish readiness early.

## 11. Initial budgets and operational controls

Starting values below are explicit engineering budgets to validate, not promises
that every possible file fits them. Expose tuning through mapper analysis settings
and record effective values in the descriptor and benchmark output.

| Resource | Initial policy |
|---|---|
| Java compiler batch | At most 100 files and 4 MiB captured source bytes; one batch active initially. |
| Java concurrency | One analysis worker initially; never CPU-count workers each holding compiler state. |
| Heap | Run scale tests with a 768 MiB mapper heap; account for AST amplification, JVM/native memory and coordinator/worker overlap separately. |
| SQLite page cache | Explicit 32 MiB maximum per mapper connection; 16 MiB per converter reader; spill sorts/work tables to disk. |
| Record/transfer buffer | Target 64 KiB inline records/chunks and <=4 MiB queued payload; large fields use streamed blobs/chunks. |
| SQL transactions | Commit by rows/bytes/time, starting at 500 records or 4 MiB, whichever is reached first. File readiness remains atomic even when a large file spans staged transactions. |
| Query pages | Keyset pagination, starting at 250 rows and a byte ceiling; no growing OFFSET scans or unbounded fetchall. |
| Progress | At least every five seconds and at bounded file/operation boundaries; track real completed work separately from liveness. |

Do not automatically retry a worker OOM with the same batch indefinitely. Record
the failing batch, reduce subsequent batch budgets where appropriate, retain
completed file facts and fail incomplete analysis explicitly when necessary.
One oversized Java source can require a separate bounded worker or an explicit
resource-limit diagnostic; do not promise an arbitrarily large AST fits fixed RAM.
Huge XML documents use streaming rows, not a hidden oversized-DOM exception.

Report discovered/hashed files, cache hits/misses, parsed files/bytes, persisted facts,
resolved references/issues, effective operation views, notes/pages, validation/import
rows, selected closure size and phase-specific elapsed time. Record Python and Java
RSS/peak RSS, configured heap/cache limits, database/temp-disk sizes and spill counts.
Do not call Windows RSS measurements heap usage, or a background heartbeat progress.

Estimate remaining time only for a known phase total after enough completed work
(for example 250 records). Update the estimate and show when it is not yet reliable;
operation views finishing does not mean note finalization/validation is finished.
Real activity resets inactivity timers. Long valid processing must not be terminated
just because a fixed wall-clock deadline passed.

## 12. Compatibility and staged delivery

Schema 4 is the scalable descriptor/index format. Preserve legacy and schema-2/3
read/export modes; do not append a giant graph to their manifests and call that the
new solution. A schema-3 compatibility manifest may be exported by streaming database
rows when explicitly requested, but the new converter path never consumes it as one
whole-project object. Very large individual old records require nested streaming
normalization or a clear regeneration requirement, never an unbounded decoder fallback.

1. **Freeze contracts and baseline:** capture current Mapper JAR/source revision,
   golden notes/manifests/workbooks, static dependency graphs and timing/resource data.
2. **Shared Java analysis:** implement AST metadata/reference parity and adapters;
   keep the stable mapper path available. Establish JDK/encoding compatibility first.
3. **Parse store and XML facts:** disk discovery, secure one-pass XML/INI facts,
   resolver cursors and staged transactions; verify existing XML semantics before
   replacing the DOM-backed catalog in the indexed mode.
4. **Indexed map production:** schema-4 descriptor, canonical notes, dependency
   graph, bounded rendering, freshness and crash-safe publication behind an explicit
   capability/format option. Do not change stable defaults yet.
5. **Consumers:** read-only indexed converter path, selected overlays, count parity,
   streamed exports and standalone reader compatibility. Select map before inventory.
6. **Incremental updates:** add/delete/change/rename and visibility invalidation;
   freeze/resume/read-concurrency and interruption tests.
7. **Scale gate and promotion:** compare correctness, boundedness and timings at all
   sizes. Promote indexed map generation/reuse only after consumers and regression
   matrix pass. Keep an explicit compatibility escape path and documented costs.

Retain existing saved config keys/enums and both run launchers. Capability detection
must distinguish old mapper JARs/maps from the new analysis format. If a map lacks a
usable Java graph, offer/document regeneration or an explicit bounded compatibility
scan; do not silently trust partial import metadata or surprise users with a global
scan after reporting a selected-only fast path. Existing maps are not mutated in place.
The wizard's legacy-layout issue discovered in testing needs a separate explicit
layout/capability decision at rollout, not an undocumented default change in phase 1.

## Expected files to change:

The following is the scoped implementation surface. New paths are marked **new**;
final class splits must follow existing modular conventions. These are future edits,
not changes authorized by saving this plan. Paths are relative to this document.

### Shared Java analysis and distribution

- [source/pom.xml](../../source/pom.xml) **new** — shared-core/mapper reactor and reproducible build ordering.
- [java-analysis-core/pom.xml](../../source/java-analysis-core/pom.xml) **new** — reusable, versioned analyzer and CLI distribution.
- [SourceAnalysis.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/SourceAnalysis.java) **new** — bounded JavacTask lifecycle and canonical reference visitor.
- [JavaMetadataExtractor.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/JavaMetadataExtractor.java) **new** — existing mapper metadata from the same parsed unit.
- [SourceSnapshot.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/SourceSnapshot.java) **new** — captured bytes, encoding, raw hash and analysis offsets.
- [SourceReferenceResolver.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/SourceReferenceResolver.java) and [TypeLookup.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/TypeLookup.java) **new** — canonical project-aware resolution shared by mapper and compatibility CLI, with bounded index lookups.
- [AnalysisRecord.java](../../source/java-analysis-core/src/main/java/il/co/dcd/javaanalysis/AnalysisRecord.java) **new** — bounded transferable fact contract; split additional record models as needed.
- [SourceReferenceScanner.java](../../source/tools/java_analysis_tools/source_dependencies/SourceReferenceScanner.java) — compatibility adapter to the shared analyzer, not a second implementation.
- [parser.py](../../source/tools/java_analysis_tools/source_dependencies/parser.py) — shared analyzer invocation for compatibility maps and unchanged bounded/cache policy.
- [resolution.py](../../source/tools/java_analysis_tools/source_dependencies/resolution.py) — explicit canonical policy/adapter and differential parity; no independent fork of visibility semantics.
- [mapper pom.xml](../../source/composer-mapper/pom.xml) — package the analyzer and pinned SQLite JDBC dependency; preserve standalone delivery.
- [generate-composer-map.cmd](../../source/composer-mapper/generate-composer-map.cmd) — build required modules and expose indexed-mode options without changing input-folder semantics.

### Mapper orchestration, storage and parsing

- [Main.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/Main.java) and [Args.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/Args.java) — format capabilities, analysis budgets, update/resume settings and bounded orchestration.
- [FileDiscoveryService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/FileDiscoveryService.java) — stream discovery into the file store; preserve channel/source ownership and filters.
- [IndexBuildService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/IndexBuildService.java), [JavaClassIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/JavaClassIndexer.java), [XmlDefinitionIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/XmlDefinitionIndexer.java), [IniMappingIndexer.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/IniMappingIndexer.java) and [Indexes.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/index/Indexes.java) — indexed-mode adapters over persisted facts; preserve legacy callers.
- [JavaClassParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/JavaClassParser.java) and [JavaClassDef.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/JavaClassDef.java) — AST-backed metadata adapter and compatibility fields.
- [OperationFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/OperationFileParser.java), [FormatFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/FormatFileParser.java) and [ContextFileParser.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/parser/ContextFileParser.java) — reuse normalized ordered facts while retaining extraction rules and bounded legacy adapters.
- [ScopedDefinitionCatalog.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/ScopedDefinitionCatalog.java) and [SourceDefinitionIdentity.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/model/SourceDefinitionIdentity.java) — query identities without retaining every DOM or rereading source for revision hashes.
- [ScopedVaultGenerationService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/ScopedVaultGenerationService.java) and [StreamingGenerationService.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/StreamingGenerationService.java) — staged generation using parsed facts, retaining mode-specific behavior.
- [ChannelImportResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/ChannelImportResolver.java), [OperationDependencyConnections.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/OperationDependencyConnections.java) and [CanonicalResourceLinks.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/CanonicalResourceLinks.java) — disk-backed effective views/calls/resources with existing precedence.
- [AnalysisStore.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/storage/AnalysisStore.java), [XmlFactReader.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/storage/XmlFactReader.java), [JavaDependencyResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/JavaDependencyResolver.java), [MapRevisionPublisher.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/storage/MapRevisionPublisher.java) and [analysis-schema.sql](../../source/composer-mapper/src/main/resources/analysis-schema.sql) **new** — normalized store, one-pass XML facts, project-aware resolution and atomic publication.
- [XmlUtil.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/XmlUtil.java), [JavaSourceReader.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/JavaSourceReader.java) and [FileUtil.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/FileUtil.java) — secure streaming/snapshot adapters and bounded hashing; preserve external behavior.

### Mapper outputs and progress

- [VaultManifestWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/VaultManifestWriter.java) — descriptor/index publication and streaming compatibility export; disk path reservations and consumer joins.
- [JavaClassMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/JavaClassMarkdownWriter.java), [OperationMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/OperationMarkdownWriter.java), [OpStepMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/OpStepMarkdownWriter.java), [FormatMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/FormatMarkdownWriter.java) and [ContextMarkdownWriter.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/render/ContextMarkdownWriter.java) — bounded final rendering, cached source digests, preserved sections and paged large relationships.
- [LinkResolver.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/LinkResolver.java), [NestedFormatInventory.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/NestedFormatInventory.java) and [MapperProgress.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/service/MapperProgress.java) — safe stable paged links/inventory and bounded phase/resource counters.
- [FormatCollectionPolicy.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/FormatCollectionPolicy.java) and [OperationStepFlow.java](../../source/composer-mapper/src/main/java/il/co/dcd/composermapper/util/OperationStepFlow.java) — preserve business algorithms; add cursor-backed adapters only where required and covered by equivalence tests.

### Converter readers, counts and compatible consumers

- [mapped_analysis_revision.py](../../source/models/mapped_analysis_revision.py) and [indexed_analysis.py](../../source/tools/composer_mapper_tools/indexed_analysis.py) **new** — bounded capability metadata and readonly indexed queries.
- [mapped_inventory.py](../../source/tools/component_inventory_tools/mapped_inventory.py) and [map_snapshot.py](../../source/tools/state_store_tools/map_snapshot.py) **new** — selected overlays, pinned map evidence and revision/validation receipts.
- [pipeline_runner.py](../../source/runtime/pipeline_runner.py) and [mapper_generation.py](../../source/tools/workspace_intake_tools/mapper_generation.py) — map-first execution and capability-aware generation, removing duplicate global analysis on the new path.
- [vault_manifest.py](../../source/tools/composer_mapper_tools/vault_manifest.py), [manifest_json_stream.py](../../source/tools/composer_mapper_tools/manifest_json_stream.py), [vault_importer.py](../../source/tools/composer_mapper_tools/vault_importer.py), [shared_vault_importer.py](../../source/tools/composer_mapper_tools/shared_vault_importer.py), [scoped_vault_importer.py](../../source/tools/composer_mapper_tools/scoped_vault_importer.py) and [scoped_intake_evidence.py](../../source/tools/composer_mapper_tools/scoped_intake_evidence.py) — indexed readiness/validation, disk joins, bounded compatibility import and no repeated full-note hydration.
- [scoped_vault_access.py](../../source/tools/composer_mapper_tools/scoped_vault_access.py), [operation-call discovery.py](../../source/tools/operation_call_tools/discovery.py), [preparation.py](../../source/tools/conversion_tools/scoped_workflow/preparation.py), [units.py](../../source/tools/conversion_tools/scoped_workflow/units.py) and [evidence.py](../../source/runtime/behavior_conversion/evidence.py) — selected, paged access through existing qualified-evidence boundaries.
- [inventory.py](../../source/tools/component_inventory_tools/inventory.py), [stored_java_dependencies.py](../../source/tools/component_inventory_tools/stored_java_dependencies.py), [conversion_scope.py](../../source/tools/component_inventory_tools/conversion_scope.py), [segmented_java_usage.py](../../source/tools/component_inventory_tools/segmented_java_usage.py), [usage_propagation.py](../../source/tools/component_inventory_tools/usage_propagation.py) and [library_planner.py](../../source/tools/component_inventory_tools/library_planner.py) — route persisted facts/graph into the existing selection/counting policy with bounded traversal.
- [component_inventory.py](../../source/tools/state_store_tools/component_inventory.py), [java_usage.py](../../source/tools/state_store_tools/java_usage.py), [workspace_analysis.py](../../source/tools/state_store_tools/workspace_analysis.py), [selected_inventory_reports.py](../../source/runtime/selected_inventory_reports.py) and [inventory_reports.py](../../source/runtime/inventory_reports.py) — selected persistence/query/report adapters and compatible revision evidence.
- [export_operation_migration.py](../../source/export_operation_migration.py), [operation-call excel_report.mjs](../../source/tools/operation_call_tools/excel_report.mjs) and [Excel Generator.py](../../Excel%20Generator.py) — both export paths, indexed/paged readers and deterministic standalone bundling without whole-project Python objects.

### Regression tests, fixtures and documentation

- [test_mapper_analysis_parity.py](../../source/tests/test_mapper_analysis_parity.py), [test_indexed_map_intake.py](../../source/tests/test_indexed_map_intake.py) and [test_mapper_analysis_scaling.py](../../source/tests/test_mapper_analysis_scaling.py) **new** — golden equivalence, selected-only loading, freshness/recovery and genuine memory-constrained stress runs.
- [test_scoped_vault_identity.py](../../source/tests/test_scoped_vault_identity.py), [test_mapper_channel_imports.py](../../source/tests/test_mapper_channel_imports.py), [test_composer_mapper_tools.py](../../source/tests/test_composer_mapper_tools.py), [test_shared_vault_intake.py](../../source/tests/test_shared_vault_intake.py), [test_scoped_startup.py](../../source/tests/test_scoped_startup.py) and [test_scoped_decorator_evidence.py](../../source/tests/test_scoped_decorator_evidence.py) — preserve mapper output, resolution, import and gate contracts.
- [test_java_source_dependencies.py](../../source/tests/test_java_source_dependencies.py), [test_segmented_inventory.py](../../source/tests/test_segmented_inventory.py), [test_inventory_scaling.py](../../source/tests/test_inventory_scaling.py), [test_source_discovery.py](../../source/tests/test_source_discovery.py) and [test_excel_export_streaming.py](../../source/tests/test_excel_export_streaming.py) — scanner/counting/visibility/export parity and bounded-loading assertions.
- [generate_huge_bank_demo.py](../../source/generate_huge_bank_demo.py) and [huge-demo generation.py](../../source/tools/huge_bank_demo/generation.py) — only extend workload controls if required to distinguish total-file and Java-file scale; do not change seed business logic.
- [mapper README](../../source/composer-mapper/README.md), [scoped_vaults.md](../scoped_vaults.md), [running_migrations.md](../running_migrations.md), [huge_bank_demo.md](../huge_bank_demo.md) and [analysis schema contract](../composer_analysis_store.md) **(last new)** — versions, capability/build compatibility, budgets, migration guidance and measured results.

Avoid opportunistic cleanup in these files. Existing compatibility implementations
stay available until their replacements pass the relevant matrix. The listing does
not authorize changes to conversion business logic, threshold policy or gate behavior.

## 13. Validation plan and release gates

### A. Semantic and product parity before performance promotion

Capture golden products from the pinned stable mapper on Bank Demo and focused
fixtures. Compare parsed semantic fields, source/usage identities, step ordering,
resolved transitions, canonical/consuming bindings, note links and workbook rows.
Normalize only genuinely volatile fields such as timestamps and checkout root paths;
do not normalize away missing references, altered source hashes or path collisions.
Check meaningful rendered Markdown/diagram differences too, not just row counts.

Cover every preservation-matrix row with an existing or new named regression. In
particular, run existing repeated-step/onlyFor/case-variant tests, keyed/indexed and
nested-format tests, hash-link tests, encoding/error tests, inheritance/override
tests, both Excel writers and copied-standalone bundling parity. Add negative cases
for malformed XML/Java, unresolved classpath, same FQCN in separate projects, comments
and unused imports, wildcard/static imports, annotations/generics, helper chains,
diamonds, cycles, multi-type files and Java 21/25 syntax policies.

Verify the missing `FormatDecoratorHolder -> Tag` dependency persists through map
generation and converter loading. Differentially compare the new graph and selected
library assignments/counts with the current converter's scanner on valid fixtures.
Review intentional AST improvements explicitly; no blanket golden-file refresh.

### B. Parse/read counts and selected-only behavior

Instrument source opens, AST/XML parse sessions, raw hashes and note-body reads by
file/revision. Assert one successful parse per changed file, zero parses for cache
hits, and no renderer/resolver reparsing. Count physical hashing reads separately.

For repeated migrations selecting different operations from an unchanged map:

- Zero full-workspace Java/XML parses in converter intake.
- Only selected/reachable detailed notes and source bodies loaded.
- Exact global counts still include unrelated consumers of selected helpers.
- No unrelated AST/document materialization, even for a heavily shared root.
- Changing one Java file reparses one file, re-resolves affected edges, and updates
  counts/notes without retaining deleted declarations or stale incoming resolutions.
- Changing an INI/import or adding a wildcard-match type invalidates dependent
  bindings even when caller bytes are unchanged.

### C. Real scale and memory, not mocked performance alone

Use actual Java parsing and actual map/consumer products at 1,000, 5,000 and 22,000
**Java source files**, with a scheduled larger case such as 50,000 when practical.
Also vary XML/operation count, high fan-in/fan-out, deep chains, repeated occurrences,
large individual XML files, giant selected closures and one oversized Java file.
The current generator's `--files` counts total fixture files, not Java files; record
both counts and do not label a 22,000-total-file fixture "22,000 Java files".

Run under fixed mapper heap and converter process limits. Initial engineering
acceptance targets are a 768 MiB mapper heap and 512 MiB converter RSS for the
representative 22,000-Java-file fixture, subject to published measurements and
explicit accounting for native/JIT/SQLite caches. Treat budgets as release tests,
not guarantees for unbounded individual files. Verify failure is diagnostic and
nonpublishing rather than an uncontrolled multi-gigabyte allocation.

Retain a synthetic 5,000-operation/shared-chain multiplicity test to expose Cartesian
explosions, but do not substitute it for real JDK/Markdown/index tests. Assert bounded
queue/cache/page high-water marks, temp-disk use, no unbounded transaction/memory
growth as total files increase, and no quadratic consumer/closure table generation.
Inspect SQL query plans for incoming/outgoing edges, consumers and note lookup.

### D. Robustness, portability and integrity

Kill/cancel generation during parse, commit, rendering and publication; reopen it
without mixed-ready output. Test deleted/changed sources during capture, corrupt
notes/index/descriptor, disk full, permission failures, Windows long paths/case
collisions, relocated checkouts, active readers during an update and missing pinned
revisions on resume. Existing published maps and configurations must survive.

Test old maps with explicit compatibility/regeneration behavior, unsupported new
schemas/capabilities with old tools, artifact packaging outside the checkout, and
network-disabled execution with allowed pre-provisioned package repositories. The
mapper must not download schemas/pricing/tokenizer data or call an AI model.

### E. Timing and go/no-go criteria

Benchmark separately: first map build, unchanged map reuse, one-file update,
converter selection/intake, count queries, rendering, validation/import and report
writing. Record bytes/rows/notes, hardware, process limits, JDK, source policy and
cache state; distinguish analysis-cache reuse from OS disk caches. Compare equivalent
ready checkpoints, not blocked legacy preflight against successful scoped intake.

First-map wall time must be measured honestly; a regression must be explained and
accepted rather than hidden by the savings in later runs. Repeated unchanged runs
must demonstrably avoid global parsing, note reimport and duplicate fact storage.
All semantic matrix tests and resource tests must pass before promotion. If they
do not, keep the stable default/compatibility path and report the exact remaining
gap. Do not remove existing features to obtain a favorable benchmark.

## 14. Completion definition

The change is complete only when one global map analysis is reusable, all current
mapper products retain their supported meaning/abilities, Java graph/count parity
is demonstrated, subsequent converter intakes load only the requested closure in
bounded pages, changes invalidate the right facts, and real tens-of-thousands-file
tests pass under declared memory limits. Merely moving the current full scan into
the mapper, adding an AST beside regex, or streaming a giant JSON into a giant
Python dictionary does not satisfy this plan.

The original planning-only restriction was superseded by the user's implementation
request. Implementation and measured acceptance results are documented in the
[indexed analysis guide](../composer_analysis_store.md).
