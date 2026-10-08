# Running migration intake

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

## Final deliverables and Gate 4

To exercise the missing runtime tests now, set `runtime_validation_mode: dummy` in the YAML profile before starting a run. The executable dummy provider calls XML, behavioral and trace test methods that always return true, emits the same passed-status fields consumed by finalization, and writes a structured report under `runtime_test_reports/<channel>/<operation>/report.json`. Reports and logs explicitly state that no requests or real comparisons occurred. The default is `disabled`; previously dummy results cannot satisfy normal-mode approval.

The pipeline calls a neutral `RuntimeTestExecutor`; provider selection is confined to that executor. Finalization consumes the ordinary passing contract without provider-specific branches. Accepted Gate 4 ends at `migration_approved`, with `production_ready: true` when its configured checks pass. This field is the computed configured-executor outcome, not independent proof of real runtime equivalence: inspect `validation_notices` and the test reports, which explicitly disclose dummy execution. Changing the configured provider invalidates saved service-validation evidence. Real Maven compilation, Maven tests, packaging, dependency guards and gate policies remain unchanged. A future real provider can implement the same boundary.

After successful service builds, runtime finalization renders the existing deployment templates, writes per-operation README files, and produces `delivery_manifest.json`, `final_report.md`, and `gate_4_report.txt`. It does not publish images or deploy to a cluster. Configure `deployment_template_dir` and `deployment_values`, keyed by `CHANNEL/OperationId`, with an explicit `image_name` and any renderer-supported port, environment or health-path values. The template directory is resolved relative to the profile.

Gate 4 requires current Gate 3 approval, unchanged generated project inputs, successful compilation/tests/packaging/IBM guards, and passed XML compatibility, behavioral equivalence and legacy trace comparison. Each behavioral category must have supporting files listed under `evidence_paths` in its persisted validation result; files must exist within the run workspace. Runtime evidence collection is not implemented yet, so ordinary build-only runs correctly stop at `finalization_blocked`, with reports explaining the missing evidence. Automatic and skip policies cannot bypass failed checks.

Use the existing approve/reject command with gate 4 when status is `gate_4_pending`. Resume rechecks deliverables and binds approval to their content fingerprints. Approval ends at `migration_approved`; it is not a deployment action. Changed deliverables require fresh approval.

Service-generation failures now persist diagnostics and prior generated output for bounded automatic retries. Budgets survive resume. Explicit `routing_mismatch` findings queue assembly corrections; `conversion_gap` and `shared_component_gap` findings require exact `component_task_ids` belonging to this run and operation (or an explicitly shared component). Upstream corrections return through Gates 2 and 3 before regenerating services. Missing evidence and unknown owners stay blocked for review rather than consuming code-generation loops. Compiler text alone is not used to infer an upstream owner. Runtime validators added later must supply these structured failure categories and ownership references.

After accepted Gate 3, resume stages each final service under the run's `services/<channel>/<operation>` directory. Approved assembly and component sources are copied unchanged; the earlier managed projects remain untouched. The model supplies wrappers, tests, resources and structured Maven dependency proposals, not a replacement POM or loose JARs. Proposals use the configured repository verifier, and the pinned Spring Boot packaging plugin creates an executable package.

Runtime persists generation attempts and input/output fingerprints. Unchanged successful projects can be reused; changed projects require regeneration, and failed attempts remain bounded across resume. Validation runs managed compilation, Maven tests and packaging with transitive dependency checks and the IBM source guard. No test reports means tests are unavailable, not passed.

Successful builds stop at `validation_evidence_pending`. XML compatibility, legacy traces and behavioral equivalence are explicitly unavailable until runtime evidence is supplied; this is not a completed migration. Runtime endpoint validation, final reporting and Gate 4 remain separate work. Structured correction routing is available, but runtime evidence producers still need integration. Mock generation requires explicit fixtures. Live model and enterprise repository execution has not been verified.
