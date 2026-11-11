# Running migration intake

For large workspaces, the configuration wizard offers **Reusable AST index for
large workspaces** when creating a map. Mapping remains global; converter intake
then loads the selected operation/dependency closure from persisted facts. See
[indexed analysis configuration, progress and reuse](composer_analysis_store.md).

## Creating and reviewing a configuration

Both `run.cmd` and `run-verbose.cmd` use the same section-based configuration
wizard. Each screen identifies the configuration and current section; long default
paths appear separately from the `Value >` input marker. **INPUT REQUIRED** means
the CLI is waiting for you. **WORKING** identifies actual discovery or saving.

Press Enter to retain a text default or accept a typed replacement. Ctrl+U clears
the saved field value; required fields still have to pass their normal validation.
Use Ctrl+B on text/checkbox screens or the Back menu action to revisit the previous
section. Back discards unfinished edits in the current section; previously committed
answers are restored. On checkbox screens, Space toggles choices and Enter on Next
accepts them. The section's Next action commits its answers to the in-memory draft.
Esc/Ctrl+C offers Continue editing or Discard configuration; closed input exits
without saving. No draft file is written.

The final Review screen initially focuses **Edit a section**, so an extra Enter
cannot save accidentally. Use Page Up/Down to scroll settings. Large operation
selections show a count and preview; **View all selected operations** opens a
filterable read-only list. Edit a section jumps directly to its saved answers and
returns to Review. Changing the source requires a fresh scope review; unavailable
channel/operation choices are removed. Unchanged discovery results are reused
within the draft. Credentials are redacted; the model key remains an environment
variable name, never a stored secret value.

Only **Save configuration** validates and writes the YAML. Replacing an existing
file requires a separate confirmation of its destination. Cancelling leaves
existing configurations unchanged. Choosing **Create a new map** records a future
action; it does not run the mapper during configuration creation. Saving also
does not start mapping, workspace intake or migration.

Choose **Start a new migration** separately. Interactive starts show the selected
configuration, source, map mode and operation scope before processing. Choose
**Start migration**, **Back to configuration selection**, or **Cancel**. Back is
initially focused. Explicit commands supplying `start --config ...` retain their
automation behavior and do not add a confirmation prompt.

For optional standalone and microservice fixture JDBC demonstrations, see
[Fixture database demonstrations](fixture-database-demo.md). Demo preparation does
not resume a stopped conversion or alter native operation logic.

## Option two conversion

Use `conversion_strategy: behavior_units` for complete-format and configured-step
conversion. `configs/internet_transfer.yaml` selects it. Start a new run with that
configuration; saved runs keep their captured strategy. The wizard also exposes
the setting, with `legacy_components` retained as its rollout default.

After intake and Gate One, Resume gathers checked evidence, reconciles typed
contracts, and generates native bundles. Request/response formats become Jackson
wire models plus transformations; each configured op-step becomes business code.
Gate Two reviews bundles and final ownership. The native service flow is assembled
and reviewed at Gate Three. Spring XML wrappers, tests, packaging and Gate Four
reuse the existing delivery path. No Composer context engine is regenerated.

New reports in stage three include `native_unit_plan.json` and
`native_bundle_results.json`. Model logs identify each unit and its queue position.
Corrections are bounded and persisted. Changed XML/source/build inputs, unresolved
behavior, missing executed tests, or missing runtime-equivalence evidence remain
explicit stops. Compile/test success alone does not approve production delivery.

See [the design](../option_two_design.md) and
[implementation record](../option_two_implementation_plan.md). JSON transport and
deterministic workflow generation remain future refinements.

## Intake and historical runtime notes

Run from the repository root with Python, PyYAML, Pydantic, and Java available:

```powershell
python -m cli start --config configs/bank_demo.yaml --run-id bank-demo-first
python -m cli status --config configs/bank_demo.yaml --run-id bank-demo-first
python -m cli resume --config configs/bank_demo.yaml --run-id bank-demo-first
python -m cli approve --config configs/bank_demo.yaml --run-id bank-demo-first --gate 1
python -m cli resume --config configs/bank_demo.yaml --run-id bank-demo-first
```

Profiles resolve paths relative to the YAML file. Copy the profile and change its
source, mapper, output, channel, and operation selections for another Composer project.
Omit include_operations to include all operations in the selected channels.

This first runtime increment executes mapping, inventory, context hierarchy,
shared classification, and planning-data preparation. It pauses before model-driven
planning; it does not yet perform conversion or claim migration completion.

Each run owns an isolated directory containing SQLite state, mapper diagnostics,
the resolved profile, inventory vault, and planning inputs. Existing directories
are rejected to prevent accidental overwrite. Outputs remain for inspection.
Resume executes model-driven planning, validates and persists the plan, writes a
Gate 1 report, and pauses for approval. After approval, resume resolves context
fields and builds dependency closures. It stops at blocked closures or at
conversion_pending. Conversion and later execution stages are still pending.

Set model_provider to gemini for native ADK Gemini execution, litellm for an
OpenAI-compatible endpoint, or mock for a deterministic planning fixture.
Mock grouping is synthetic and does not represent a model conversion or review.
Compatible endpoints require google-adk[extensions], model_base_url, model_name,
and a credential in the environment variable named by model_api_key_environment.
Native Gemini uses the standard ADK Google authentication configuration.

Java classpath discovery reads Eclipse library and variable entries and accepts
additional classpath_jars plus eclipse_classpath_variables in the YAML profile.
Configured paths are relative to that profile. Set JAVA_HOME to the desired JDK
to inventory its platform classes. No dependencies are downloaded automatically.
The run saves java_classpath_index.json with class locations and diagnostics.
Unresolved containers, missing or invalid JARs, ambiguous imported classes, and
wildcard imports block closure for review. JAR-only implementation classes require
source or an explicit retention decision; this runtime does not yet implement that
retention workflow or generate Maven coordinates from JAR files.
The inventory covers explicit imports and their source dependencies; fully
qualified references, reflection, implicit types, and compiler-level symbol
resolution still require build validation. Multi-release-only JAR entries are not
used to infer target-version availability.

## Managed Maven dependencies

The first managed-POM integration is available through Python APIs. Initialize a
service or common-library POM with initialize_managed_pom, then give its path and
a trusted verifier to run_ibm_java_cleaner_task. Select
MANAGED_IBM_CLEANER_INSTRUCTION for that model invocation. Managed conversion
returns JSON containing java_source and dependencies, with group_id, artifact_id,
version, scope, reason, and required_classes for each proposal.

MavenRepositoryVerifier uses Maven's normal user and installation settings,
repositories, mirrors, credentials, and local cache. It resolves target artifacts and checks
requested class entries. No source-analysis downloads are introduced. Repository
verification has not been exercised against an enterprise repository in tests.
An existing local Maven cache must be trusted; this verifier does not establish
the origin of previously cached artifacts or prove method-level API compatibility.

merge_dependencies rejects direct legacy-runtime dependencies, version/scope
conflicts, dynamic versions, and local systemPath references. Exact IBM client
coordinates may be approved explicitly. Existing broader IBM source and project
guards remain in effect for callers without a managed context. Managed source,
review, generation, assembly, and validation paths accept exact approved client
imports; resolved transitive artifacts are inspected before managed compilation.
The manager writes under a process lock and atomically replaces the POM. An audit
intent records proposals and the resulting POM hash. Compare that hash with the
actual POM after interruption; do not assume every intent committed. A lock left
by a crashed process requires operator inspection before removal.

In managed mode, Java output belongs in the project's src/main/java, and Maven
compiles all available project sources. Final service generation accepts the same
managed_pom_path and preserves that POM; prepare its complete Spring Boot/common-lib
baseline before generation. Plain-source callers retain their existing behavior.
Managed context and XML DTO converters also accept a shared ManagedBuildContext.
Context output uses java_source and dependencies; XML DTO output additionally
includes service_layer_requirements. The verifier's compile_project inspects the
resolved dependency tree before compilation, rejecting prohibited transitives.
Build, service generation, validation, and common-library build APIs accept this
context so repository routing and policy remain consistent.

Managed conversion starts after READY closure checks using Maven's normal configuration.
Optional maven_settings_path and maven_local_repository values override Maven defaults;
approved_maven_repository_urls is retained for older profiles and is no longer enforced.
Runtime creates service/common-lib POMs and dispatches
context, DTO, and Java implementation tasks to their managed projects. Dependency
conflicts and source/build failures remain blocking results. Mock conversion
requires explicit fixtures rather than fabricated source. IBM exceptions use
allowed_ibm_artifacts (exact coordinates) and allowed_ibm_classes (exact imports);
Composer runtime classes remain prohibited even if listed.

POM checkpoints mark affected build results and prior component artifacts
needs_rerun when their POM changes. Shared-library changes invalidate service
build results throughout the run. The component compiled against the new POM is
excluded from that invalidation. Repository-backed execution remains unverified
without enterprise settings and credentials. Assembly, full service-generation
orchestration and later human gates
still require runtime integration; this is not a complete migration runner.
Shared conversion tasks run before operation tasks. The common library is installed
through the managed verifier into the configured Maven cache before service
conversion starts, and each service POM references that generated module.

## Component review and Gate 2

After managed conversion, runtime reviews every scheduled component against the
exact input snapshot stored with its conversion task. Structural checks and a
configured model review must both pass. Mock review requires an explicit fixture;
there is no automatic fabricated approval. Low-confidence results, TODOs, missing
or stale artifacts, missing expected tasks, and unreviewed Java files block Gate 2.
Required framework formatter/decorator mappings must have reviewed shared
components; Gate 2 does not silently waive gaps in framework conversion coverage.

Review snapshots are keyed by input, generated-source, POM, model, and policy
fingerprints. Revision feedback is added to the existing task and sent back through
managed conversion. Persisted revision counts prevent resume from restarting the
retry budget. Unresolved reviews and build failures pause at
component_review_blocked for operator intervention.

Runtime writes gate_2_report.txt, including individual findings and code/POM
fingerprints. Use the existing approve or reject command with --gate 2, then resume.
Configured automatic/skip policies still require all review and build checks to
pass. Changed evidence invalidates the previous report approval. Successful Gate 2
continues into operation assembly. Gate 2 builds only its reviewed component files
in a temporary project with the canonical POM; assembly-owned files are assessed
by assembly, so a failed assembly does not prevent component-gate recovery.
Model and repository execution has not been verified live by the unit tests.

## Operation assembly

After current Gate 2 approval, runtime builds and persists routing, context, and
serialization plans from each READY closure. The assembly model receives the
original operation XML, plans, and actual approved component source/API definitions.
It returns a service skeleton and verified dependency proposals. The skeleton is
written into the operation's managed Maven project and compiled there.

The implementation inserter fills six method bodies in sequence. Each pass may
change only its requested method body, and it compiles against the same POM.
Leftover TODOs or UnsupportedOperationException stubs block completion even when
the compiler accepts them. Missing collaborators and model/build failures remain
blocking; no placeholder business implementation is accepted as successful.

assembly_results.json records per-operation results. Successful checkpoints include
plan/component input fingerprints, service hashes, and POM hashes. Unchanged
successes are reused on resume; changed output is rebuilt. Assembly dependency
changes require current Gate 2 approval again. Failed attempts use a persisted
retry budget and stop at assembly_blocked when unresolved. Other operations are
still processed, but the run cannot progress unless all selected operations assemble.
Successful assembly continues to operation equivalence review and Gate 3.

## Operation review and Gate 3

Runtime checks every selected operation/channel pair against its successful
assembly checkpoint. Review inputs include current original operation XML,
routing/context/serialization plans, approved component APIs, assembled Java,
and the canonical POM. Missing, changed, or uncompiled evidence blocks progress.
The reply type is taken from the actual converted reply DTO when available.

Structural checks and a configured model review are combined. A model approval
cannot override structural findings, prohibited dependencies, or low confidence.
Static/model review is not proof of runtime equivalence to the legacy service.
Resolved findings, input fingerprints, and correction attempts are persisted
per operation and channel. Fixable findings are sent back as assembly feedback;
retry budgets survive resume. Missing evidence and exhausted corrections pause
at operation_review_blocked for operator intervention.

The run writes gate_3_report.txt with individual findings, fingerprints, and build
results. Use the existing approve/reject command with --gate 3, then resume.
Automatic/skip policies still require every selected operation to pass review
and compilation. Changed XML, code, plans, components, or POM require review
and approval again. Successful Gate 3 ends at service_generation_pending;
full service-generation orchestration is the next integration segment.

gate_policies maps gate numbers (quoted strings in YAML) to human (default),
automatic (continue after checks pass), or skip (skip human review after checks).
Only Gate 1 is wired in this increment. Decisions are tied to the report content;
changed reports require new decisions. Rejections remain effective until replaced
by an explicit approval. Run profiles are snapshotted at start for reproducibility.
# Service generation and build validation

## Segmented inventory and diagnosing long intake

Selection is resolved before Java-use evidence expansion. Detailed operation-times-
reference-site records are created only for selected operations and required
callees. Exact global sharing counts for their reachable components are stored as
two compact relations: configured root/operation multiplicities and root/target
reference multiplicities. The planner joins these factors when it needs consumer
counts. It does not persist the Cartesian expansion for unrelated operations.
Direct configured-use metadata and the global Java source graph remain available;
a cold global syntax pass is still required to establish exact sharing counts.

Global roots that cannot reach a selected target are skipped during propagation.
Graphs up to 100,000 distinct class-to-class links use bounded compact adjacency
with exact reference-site weights to avoid a SQL statement per traversal step;
larger graphs retain the disk-backed traversal. Repeated sites do not force a
small class graph into the slower traversal path.
Existing cycle semantics and integer reference multiplicities are preserved.
Requests outside a run's detailed operation scope fail explicitly rather than
silently planning with incomplete dependency evidence. Older detailed inventories
remain readable.

Repeated class/project ownership lookups are cached for the immutable workspace
snapshot. The operation-reference pass reads operation bodies only, rather than
rehydrating every format, context and step a second time.

During inventory, console progress names the active phase and completed work.
`logs/intake.log` records stage messages, `logs/intake-progress.json` records the
latest phase/count/last-work evidence, and after 120 seconds without completed
work `logs/intake-stacks.log` captures Python thread stacks for diagnosis. These
snapshots do not kill a valid long-running scan or reset the scanner inactivity
timer. The workspace Java-file total is labeled as an index total, not a completed
count or the requested conversion scope.

## Large workspaces and selected conversion scope

Intake uses a temporary SQLite inventory spool, canonical XML content records,
row-based dependency storage, and incremental JSON report writes. Reports keep
their existing filenames and field schemas. Detailed report arrays contain the
selected/required closure; their analysis-scope fields state this explicitly.
Usage counts for reported components still include every workspace consumer.
The complete global inventory remains in the run database;
`conversion_scope.json` identifies selected operations, required called operations,
reachable Java implementations, missing calls and explicitly excluded required
operations. Existing operation-selection/preflight policies still decide which
called operations may be scheduled; this report does not silently broaden them.

Java syntax is parsed sequentially in batches of at most 250 files or 8 MiB of
source input (a single larger file is processed alone). Python consumes source
records incrementally. Exact global dependency-use counts are propagated with
SQLite work queues and cached per-root path counts, retaining existing cycle
handling and sharing thresholds. Conversion evidence reads fetch only the
selected operation's reachable implementations. Library placement still uses
workspace-wide consumers and reference multiplicities, including other channels.

The first run must discover global dependencies to preserve those counts. Later
runs reuse content-verified syntax from `<output_root>/.workspace-analysis/`.
Source bytes and parser policy determine reuse. Reference resolution is repeated
against the current project/class index, so added/deleted classes and changed
visibility cannot reuse stale resolutions. XML/channel metadata is rediscovered.
Complete workspace revisions include source/XML/project metadata fingerprints and
are bound in each run database; changed inputs during analysis prevent publication.
Interrupted work may reuse complete per-file syntax, never partial global counts.
Older run databases retain their existing graph-reader compatibility.

Console diagnostics record Python resident/peak memory, maximum observed Java
scanner resident memory, batch/cache counts, and report-writing stages. Disk space
still scales with global reference/use evidence; the compact class index and a
single source/XML document can still grow with input size. The 22,000-record
scaling test bounds Python allocations for spooling/reporting, not the complete
memory requirement of an arbitrary 22,000-file enterprise repository.
An additional stress fixture discovers 22,001 real source files with synthetic
syntax results, verifies 220 global consumers across ten channels, and checks
that a selected operation loads only its two reachable implementations. It caps
traced Python allocations at 192 MiB; actual JDK parsing is verified separately
on smaller fixtures. Neither limit is a whole-process guarantee for arbitrary
source sizes or dependency closures.

## Java dependency scanner progress and inactivity timeout

New-config creation prompts for `java_scan_inactivity_timeout_seconds`, default
`900` (15 minutes). Enter accepts the default; a positive whole number overrides
it. Existing profiles also use 900 unless they explicitly configure this field.
The setting is saved with the run and applies to Java dependency scanning during
intake and continuation.

This is an inactivity limit, not a total scan duration. Scanner stdout/stderr
activity or changes to its result file reset the timer, so a progressing scan of
22,000 or more files can run longer than 15 minutes. The scanner reports actual
parsed/scanned file counts at least every 100 files, or after five seconds when
a file finishes. The general inventory heartbeat does not reset this timer.
A single file with no observable progress can still hit the inactivity limit.

Inactivity errors identify the configured idle period; executable/access errors
identify failure to launch or access the JDK scanner. Nonzero Java exit codes
retain the scanner's stderr diagnostics.

## Reusing an existing Composer map

In **Create a new config**, choose **Create a new map** (the default) to keep
generating `<run>/vault`, or **Use an existing map folder** to import a completed
Composer Mapper output directly. Reuse mode skips the Mapper JAR prompt and
execution; it does not copy or modify the external map. The source workspace is
still required for Java discovery and component inventory.

The saved YAML contains `existing_composer_map: "D:/ComposerMaps/MyWorkspace"`.
Config creation, saving, loading, and intake startup check only that this folder
and its manifest or legacy registry exist. They do not scan note contents.
The map is fully validated once at the import boundary, with counting, progress,
and time estimates; selected channels are checked there. Import helpers reuse
that validated manifest. Targeted integrity checks still detect evidence changes
during import. Validation results are not cached across separate imports.
Relative map paths resolve against the YAML file's directory. The folder must be
a supported legacy/scoped/shared vault and contain the selected channels. Its
resolved location is persisted with the run for continuation; keep the map
available and unchanged while the migration is in progress. Leave the setting
absent or null to preserve new-map generation. No `<run>/vault` or mapper log is
created in reuse mode.

## Operation without public website access

### Conversion AI diagnostics

Run `diagnose-run.cmd` and choose a saved run, or supply its folder as an argument.
At conversion checkpoints the command reports AI activity per conversion target
(basic format, decorator, configured format, OP step, shared component or unit),
including consuming operations. It skips earlier boundary/indexing investigations.
Pre-conversion preparation checkpoints retain the boundary diagnostic. Other stages
are identified without running an unrelated earlier-stage investigation.

The report separates request budget checks, generation/correction attempts, delivery
retries, and saved validation/reuse results. An oversized check is not a transmitted
request. Received text, HTTP 200, valid JSON, component build/tests and whole-unit
acceptance are separate facts. Missing HTTP status stays `not captured`; unfinished
attempts stay `in_progress_or_unknown`. Saved receipts are evidence of the recorded
outcome, not a new verification of source freshness or whole-operation equivalence.

Console output and `work/diagnostics/<run-name>/conversion-ai-summary.txt` summarize
the history. `conversion-ai-summary.json` and readable target files under `targets/`
retain attempt references. `materials/<content-hash>/` holds available `request.json`,
`instructions.txt`, `response.txt`, redacted `error.txt` and extracted sources with original filenames
where provenance resolves them. Identical application material is shared by hash;
the request itself is not deduplicated or changed. Existing oversized exports remain
available alongside the report. Exports do not change the saved run or retry budgets.

The command also writes `work/diagnostics/<run-name>/index.html`. Open it directly
in a browser; its styling, navigation, filters and report data are local files under
`assets/`, so no web server or internet access is required. Keep that folder with
the page when copying the dashboard. Rerun the diagnostic to refresh the snapshot.

The dashboard starts with the same stage checklist as the menu progress display.
During AI conversion it defaults to failures and blockers, with filters for status,
component type, consuming operation and format/unformat direction. Component details
link prerequisites and dependents, distinguish conversion attempts from delivery
retries, and link captured request, instruction, response and error files. HTTP status
and unrecorded evidence remain explicitly unknown. A saved validation result is not
automatically whole-component or whole-operation acceptance.

The collapsed saved-evidence view reads existing source-index and boundary-analysis
reports without rerunning those stages or opening original workspace sources. Indexed
classes and analyzed boundaries are labelled separately from native conversion results.
Reports exceeding the 32 MiB dashboard metadata limit are explicitly skipped. Existing
reports, captured requests and generated files can change during an active run; this is
an observation, not an atomic snapshot of all filesystem artifacts.

`Show exported files` lists materials referenced by the current snapshot. Folder links
depend on browser support; the copyable folder path is the reliable way to open the
directory in Explorer. Conversion diagnostics no longer invoke the legacy oversized
exporter after the AI report. Old hash folders and other diagnostic files are retained,
but are not included just because they already exist in the export directory.

Future runs retain correlated events in `reports/model_attempts/events.jsonl` and
exact application text in its checksum-addressed `blobs/` folder while model
diagnostics are active. API credentials and transport headers are not captured.
Native adapter HTTP hooks capture status and request identifiers when exposed;
LiteLLM/provider versions that do not expose them leave status unknown. Capture
failures warn without changing model execution. Full prompts and source/response
text stay in local materials, not the console summary.

Historical runs are diagnosed from existing database rows, reports, captures and
incrementally read logs. Historical request rows may include later validation
feedback. Missing instructions or exact transport details are not reconstructed.
Staged reservations and generation rows are not counted as separate requests;
ambiguous legacy log lines are reported as uncorrelated rather than assigned by
guesswork. The diagnostic can run during conversion; its observation time is shown,
and later activity may not yet be present. It performs no AI calls, Java builds,
original-source parsing, connector reads, or migration-state writes.

`run.cmd` and `run-verbose.cmd` default `LITELLM_LOCAL_MODEL_COST_MAP=True`,
which makes LiteLLM use its bundled model pricing metadata. An explicitly set
environment value takes precedence. When launching Python directly, set this
variable before starting the process (PowerShell):

```powershell
$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"
```

Kubernetes validation uses the official Kubernetes v1.34.0 OpenAPI schema bundled
at `source/tools/deployment_tools/schemas/kubernetes-1.34.0.json`. Its upstream
provenance URL and SHA-256 remain in the validation report. The schema is copied
to the existing validation cache on first use; validation never downloads it.
Other versions require a matching bundled or pre-populated cached schema.

The converter measures model requests in characters and UTF-8 bytes; it does not
call a tokenizer for this budget. LiteLLM may still use tokenizers internally to
estimate usage/cost when the endpoint does not return token counts.

LiteLLM execution prepares a local tokenizer cache before importing the adapter or
starting model retries, including when Python is launched directly. The repository
bundles `cl100k_base` and `o200k_base` under
`source/runtime/model_execution/tokenizer_assets`, with upstream URLs, SHA-256
checksums, license and tested dependency versions. Pull/copy this directory with
the code; no tokenizer download is needed on the enterprise machine.

The default cache is `<Snapir root>/work/cache/tokenizers`. Set
`TIKTOKEN_CACHE_DIR` or `CUSTOM_TIKTOKEN_CACHE_DIR` to select another directory.
If both are set, they must resolve to the same location. `DATA_GYM_CACHE_DIR` is
honored when neither is set. Empty paths are rejected because they disable
caching. Preparation sets both tiktoken and LiteLLM cache variables so LiteLLM
cannot silently replace the selected path. Missing or damaged cache entries are
rebuilt atomically from verified bundled data.

Missing/corrupt bundled data, cache permission errors, or incompatible tokenizer
initialization stop execution with an `Offline tokenizer setup failed` message
before a model attempt. Restore the bundled directory from the repository and
check the selected cache permissions and installed dependency versions. Git
attributes preserve the tokenizer bytes across Windows/Unix checkouts; do not
edit their line endings. Public data fetching through tiktoken is disabled after
preparation: another encoding requiring an uncached asset fails rather than
downloading. Additional provider-specific tokenizers, such as Hugging Face
tokenizers, require separately provisioned assets; this is not a blanket offline
mode for every LiteLLM provider. Native Gemini and mock execution are unchanged.
The model endpoint must still be reachable, and its transport failures retain
the existing retry behavior. Character budgets remain estimates, not Gemini
token counts, and are not changed by this cache preparation.

Configure pip and Maven to use accessible package repositories, the model profile
to use the on-premises AI endpoint, container images to use the internal registry,
and deployment/test settings to use reachable OpenShift, services and databases.

## Closure integration smoke test

### Source identity and configured-use inventory

### Shared-library placement and component reuse

The ownership planner now saves `shared_library_plan.json` and includes it in Gate 1. Configure `shared_library_min_usage: 5` and `broad_library_usage_threshold: 10` (the defaults). Fewer than five recorded source references remain operation-local; five through ten go into a smaller shared library grouped by consumer set; more than ten go into common-lib. Counts span the supplied workspace, not just selected operations, and are not runtime invocation counts. The broad threshold must be at least the small-sharing minimum.

Planned conversion task identities follow original source/definition identity and library ownership, not the calling channel. Each library has its own managed POM; selected consumers receive its pinned, run-owned draft version. Known formatter/decorator source classes are queued alongside step classes. Formats use their inventoried original XML rather than mapper note text. Gate 2 reviews the planned library projects and registers accepted native components. Conversion consults the existing artifact registry and verifies saved input, generated-source and POM hashes before reuse; changed/missing output or feedback prevents reuse. Below-threshold components are generated locally for each operation instead of being moved into a shared JAR.

Assembly receives the relevant converted components and library identities, and component coverage checks use their declared consumer operations across channels. Operation-local tasks cover only their own operation, even if their source has other consumers. Existing runs without the new inventory/library plan retain their previous scheduling path. Method-level usage discovery, compiler-level symbol attribution, immutable artifact publication and cross-run registry storage remain separate implementation work. Library versions are run-owned drafts installed locally, not published production releases.

There is no separate inline-decision or template-insertion stage. Usage thresholds govern local versus shared-library placement; Java implementation choices belong to the model within that ownership. The current component conversion contract still generates classes, so allowing operation-local logic to become direct statements or local helper methods instead of separate classes requires its own integration. No pre-conversion class-skipping mechanism is implemented.

Intake additionally scans the entire supplied workspace, before selected-operation filtering, and writes `component_inventory.json`, `component_usage.json` and `configured_component_usage.json`. Additive SQLite tables store originating Java implementations, original configured definitions, each operation's configured uses and inventory diagnostics. Implementation identity uses workspace identity, workspace-relative source root/file, package/class and an optional exact method signature; source hash is stored separately. XML parameters, fields, decorators and routing remain separate configuration records and hashes. The same source can have many consumers without duplicate implementation records; different source locations are not merged merely because class names or content match.

Set `source_workspace_id` to a stable project identifier when equivalent checkouts may move between machines or folders. Without it, the resolved workspace location identifies the workspace. Usage reports distinguish reference count, distinct original operation definitions and distinct channels, and retain unused configured definitions with zero uses. Channel-import mappings retain their originating configuration file; missing or ambiguous sources are explicit unresolved bindings, not fabricated implementations.

### Java utility dependencies

Intake now runs a bundled syntax scanner using an installed JDK 17 or later and writes `java_source_dependencies.json`. The JDK parses source without executing workspace code, running annotation processors, attributing symbols, compiling the legacy workspace, or downloading dependencies. Parser manifests and reports use a self-cleaning temporary directory. SQLite stores resolved source-reference sites, indirect operation uses, and scoped resolution diagnostics.

Imports establish candidate names; unused imports, comments and strings do not count as utility uses. The scanner covers declared types, inheritance/interfaces, constructors, casts, annotations, generics, class-qualified calls/fields, method references and static imports. Resolution handles explicit imports, same-package names, fully qualified types, enclosing source files, and source candidates from wildcard imports. Different source copies retain their original identities and project visibility; ambiguous references are not resolved by picking the first file.

Each original XML use carries its operation/channel consumers through the reachable source graph. Reports distinguish direct references from inherited source-use counts. In an acyclic graph, multiple source-reference sites contribute their multiplicity to downstream utility uses, without enumerating every path. These are static source-use expansions, not observed invocation frequency or a claim that every branch executes. The existing configurable thresholds apply to these utility counts too; no ownership threshold is silently changed.

Gate 1 now includes dependency-first component conversion, dependencies between generated libraries, and their build order. Selected source ambiguities, source/library cycles, or a shared project requiring an operation-local class block planning for review. Unrelated source diagnostics remain in the inventory report. Library grouping can itself create a cycle even when the Java graph is acyclic; that conflict requires a reviewed placement change rather than guessed build order.

Conversion queues reachable source utilities once for a planned shared library, or separately per operation below the sharing threshold. Utilities compile before callers, and a library is installed before another library that needs it. Generated POMs receive the planned pinned library dependencies; services consume their required utility libraries. Caller model requests include the already converted utility APIs and instruct the model to call those APIs, not recreate their implementations. Gate 2 checks utility coverage, dependency order, original dependency hashes, and current native APIs; changed or missing evidence blocks acceptance. Source changes require refreshed inventory and rescheduling, and transitive source hashes prevent unchanged callers from retaining stale dependency inputs.

This is conservative source-type discovery, not a complete Java method call graph. Reflection, dynamically constructed names, runtime dispatch, overload attribution, and binary-only implementations remain outside this inventory. Existing classpath/closure checks and managed Maven compilation still run; source availability or graph resolution alone does not prove a successful build or preserved behavior. Live model and enterprise repository execution remains unverified.

Run `python smoke_tests/closure_smoke_test.py` after rebuilding the mapper JAR. This creates a temporary Bank Demo vault and database, performs inventory/planning preparation and dependency closure without model calls, prints genuine remaining blockers, and deletes the temporary run automatically. Success verifies shared-format import, tag mapping and per-step implementation coverage; it does not imply every dependency is resolved.

Selected-channel mapper discovery now follows declared `dse.ini` channel imports and processes imported definitions before local overrides. Missing imports, cycles and duplicate channel definitions are errors. Channel notes include effective tag mappings for the existing vault importer. Closure checks match each step to its implementation rather than assuming one unique class per step, and repeated validation does not duplicate identical findings.

Bank Demo's selected operation now resolves its shared error format and formatter/decorator tags. It still requires explicit replacement decisions for unavailable `com.ibm.dse.base.CCOperationStep` and `com.ibm.dse.base.Context` APIs. These remain blocked; no fake framework mapping was added.

## Microservice creation and Gate 4

Operation assembly prepares an editable `values.yaml` in the native operation root before Gate 3, without an approval gate for creating that file. Blank JDBC URL and driver settings are filled only from the operation's unambiguous Composer pool configuration; credentials remain Secret references. Missing or unsafe settings are reported in `operation_values_results.json`. Gate 4 reviews that file and the accepted operation before Spring Boot wrapper or Helm template creation. Approval is followed by Resume. Helm uses this same root file through `--values`; no separate microservice-deployment definition is generated. Gate 5 reviews the built and validated result.

## Final deliverables and Gate 5

To exercise the missing runtime tests now, set `runtime_validation_mode: dummy` in the YAML profile before starting a run. The executable dummy provider calls XML, behavioral and trace test methods that always return true, emits the same passed-status fields consumed by finalization, and writes a structured report under `runtime_test_reports/<channel>/<operation>/report.json`. Reports and logs explicitly state that no requests or real comparisons occurred. The default is `disabled`; previously dummy results cannot satisfy normal-mode approval.

The pipeline calls a neutral `RuntimeTestExecutor`; provider selection is confined to that executor. Finalization consumes the ordinary passing contract without provider-specific branches. Accepted Gate 5 ends at `migration_approved`, with `production_ready: true` when its configured checks pass. This field is the computed configured-executor outcome, not independent proof of real runtime equivalence: inspect `validation_notices` and the test reports, which explicitly disclose dummy execution. Changing the configured provider invalidates saved service-validation evidence. Real Maven compilation, Maven tests, packaging, dependency guards and gate policies remain unchanged. A future real provider can implement the same boundary.

After successful service builds, runtime finalization renders the existing deployment templates, writes per-operation README files, and produces `delivery_manifest.json`, `final_report.md`, and `gate_5_report.txt`. It does not publish images or deploy to a cluster. Configure `deployment_template_dir` and `deployment_values`, keyed by `CHANNEL/OperationId`, with an explicit `image_name` and any renderer-supported port, environment or health-path values. The template directory is resolved relative to the profile.

Gate 5 requires current Gate 3 approval, unchanged generated project inputs, successful compilation/tests/packaging/IBM guards, and passed XML compatibility, behavioral equivalence and legacy trace comparison. Each behavioral category must have supporting files listed under `evidence_paths` in its persisted validation result; files must exist within the run workspace. Runtime evidence collection is not implemented yet, so ordinary build-only runs correctly stop at `finalization_blocked`, with reports explaining the missing evidence. Automatic and skip policies cannot bypass failed checks.

Use the existing approve/reject command with gate 4 when status is `gate_4_pending`. Resume rechecks deliverables and binds approval to their content fingerprints. Approval ends at `migration_approved`; it is not a deployment action. Changed deliverables require fresh approval.

Service-generation failures now persist diagnostics and prior generated output for bounded automatic retries. Budgets survive resume. Explicit `routing_mismatch` findings queue assembly corrections; `conversion_gap` and `shared_component_gap` findings require exact `component_task_ids` belonging to this run and operation (or an explicitly shared component). Upstream corrections return through Gates 2 and 3 before regenerating services. Missing evidence and unknown owners stay blocked for review rather than consuming code-generation loops. Compiler text alone is not used to infer an upstream owner. Runtime validators added later must supply these structured failure categories and ownership references.

After accepted Gate 3, resume stages each final service under the run's `services/<channel>/<operation>` directory. Approved assembly and component sources are copied unchanged; the earlier managed projects remain untouched. The model supplies wrappers, tests, resources and structured Maven dependency proposals, not a replacement POM or loose JARs. Proposals use the configured repository verifier, and the pinned Spring Boot packaging plugin creates an executable package.

Runtime persists generation attempts and input/output fingerprints. Unchanged successful projects can be reused; changed projects require regeneration, and failed attempts remain bounded across resume. Validation runs managed compilation, Maven tests and packaging with transitive dependency checks and the IBM source guard. No test reports means tests are unavailable, not passed.

Successful builds stop at `validation_evidence_pending`. XML compatibility, legacy traces and behavioral equivalence are explicitly unavailable until runtime evidence is supplied; this is not a completed migration. Runtime endpoint validation, final reporting and Gate 5 remain separate work. Structured correction routing is available, but runtime evidence producers still need integration. Mock generation requires explicit fixtures. Live model and enterprise repository execution has not been verified.
