# snapir

## Java toolchain

Generated components, shared libraries, and operation services default to Java 25; each migration can select Java 21 or 25 with `java_version` and `java_home`. The app verifies the selected JDK and supplies it to Java and Maven processes. Generated POMs enforce that run's JDK version and compiler release; use separate runs for different targets. Composer mapper remains a Java 25 tool. Spring Boot is pinned to 3.5.16, whose [official requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html) include Java 25 compatibility.

## Project layout and direct commands

### Option two: native behavior units

Set `conversion_strategy: behavior_units` to use the new conversion path. The
Internet Transfer configuration selects it explicitly. The configuration wizard
offers both strategies; existing profiles without this field remain on
`legacy_components`. Start a new run to use Option Two: changing a YAML file does
not replace the strategy saved in an existing run.

Discovery still gathers the operation's XML and supporting source. Conversion
then handles complete request/response formats and configured op-steps rather
than generating one class for each legacy component. Formats produce Jackson XML
wire models and explicit mapping methods. Steps produce native business code.
Shared typed contracts connect those bundles to an ordinary Java service flow;
Spring wrappers call the request mapper, service, and response mapper.

The existing seven stages, review gates, placement thresholds, selected JDK,
Maven repository settings, and grouped model diagnostics remain. Compatible
complete units count distinct operation/channel consumers across the discovered
workspace. Contract-incompatible uses split before final ownership is assigned.
Native projects pin a JUnit-capable test runner. Candidate bundles must compile,
execute their required tests, and pass behavior review before approval. Saved
attempts and source/build manifests support Resume and reject changed evidence.

The [design](option_two_design.md) and
[implementation record](option_two_implementation_plan.md) describe the new
modules and contracts. XML is the initial transport; JSON mapping and deterministic
workflow generation remain future refinements. Offline fixtures validate the
pipeline and representative Jackson behavior, but do not establish full
bank-demo or production equivalence.

Application packages, tests, templates, and the mapper live in `source/`.
Project data stays in root `configs/`, `bank-demo/`, `docs/`, and `work/`;
`requirements.txt`, `.venv/`, and `run.cmd` also stay at the root.
`run.cmd` works from any directory and launches Python with `source/` as its working directory.
For direct commands, start at the project root:

```cmd
cd source
..\.venv\Scripts\python.exe -m cli --help
..\.venv\Scripts\python.exe -m cli status --config ..\configs\bank_demo.yaml
..\.venv\Scripts\python.exe -m pytest tests -q
..\.venv\Scripts\python.exe smoke_tests\inventory_smoke_test.py
..\.venv\Scripts\python.exe smoke_tests\closure_smoke_test.py
cd composer-mapper
mvn package
```

In IntelliJ, mark `source/` as **Sources Root** and use the root `.venv` interpreter.
The project root is not a Python package; no root import-path entry is required.
Existing saved profiles are not rewritten and may still contain the former mapper path.


Deployment manifests reference a supplied `image_name`; they do not build or inspect that image. Supply an image running JRE/JDK 25 and verify `java -version` inside it before deployment. Legacy source build metadata and third-party dependency bytecode targets remain unchanged.


## Migration run folder contents

Each migration run has its own folder under `work/migration_runs/<run-id>` (or the configured `output_root`). The table below describes the artifacts produced by a successful deterministic intake and legacy analysis stage.

After intake, the run pauses at `planning_inputs_ready`, before model-driven migration planning. These artifacts describe the legacy workspace and prepare planning inputs; generated services are added in later stages. Failed or earlier paused runs may contain only some of these artifacts.

| File or folder | Contents |
| --- | --- |
| `vault/` | Mapper-produced Markdown describing the legacy workspace: operations, operation steps (`opsteps/`), Java classes, contexts, formats, channels, and analysis. |
| `generated/` | Migrated application output area; generated services are added in later stages. |
| `reports/1_intake_and_legacy_analysis/run_config.json` | Effective run settings snapshot, also persisted in the database. |
| `state/profile.json` | Validated project configuration snapshot with resolved paths. |
| `reports/1_intake_and_legacy_analysis/java_source_index.json` | Discovered Java source files and any source discovery issues. |
| `reports/1_intake_and_legacy_analysis/java_classpath_index.json` | Discovered Java classpath information, including compiled types, libraries, and discovery issues. |
| `reports/1_intake_and_legacy_analysis/component_inventory.json` | Legacy components and their relationships. |
| `reports/1_intake_and_legacy_analysis/java_source_dependencies.json` | Dependencies between Java source components. |
| `reports/1_intake_and_legacy_analysis/component_usage.json` | Implementation component usage. |
| `reports/1_intake_and_legacy_analysis/configured_component_usage.json` | Component usage identified through legacy configuration. |
| `reports/2_migration_planning/planning_inputs.json` | Operation summaries ready for migration planning. |
| `state/migration.db` | SQLite database containing run state and structured analysis. |
| `logs/mapper.log` | Captured mapper standard output and standard error. |

Continuation requires `state/` and the mapper inputs in `vault/`; intake inspection reports are optional for continuation. Original sources remain external to the run folder. Reports are grouped by the seven workflow stages below. Approval uses the relevant stage's review reports and evidence.

| Workflow stage | Folder under `reports/` | Main reports and approval gate |
| --- | --- | --- |
| Intake and legacy analysis | `1_intake_and_legacy_analysis/` | Run settings, source discovery, component inventory and usage. |
| Migration planning | `2_migration_planning/` | Planning inputs, `shared_library_plan.json`, `gate_1_report.md`, and the linked `gate_1/` report bundle and manifest. Gate One reviews the plan. |
| Dependency closure and component conversion | `3_dependency_closure_and_component_conversion/` | `dependency_closure.json` records required components and blockers; `managed_conversion_results.json` records conversion results. |
| Component review | `4_component_review/` | `gate_2_report.txt` reviews converted components. |
| Operation assembly and review | `5_operation_assembly_and_review/` | `assembly_results.json` and `gate_3_report.txt` review assembled operations. |
| Service generation and validation | `6_service_generation_and_validation/` | `service_validation_results.json` and `runtime_test_reports/` hold validation evidence. |
| Final validation | `7_final_validation/` | `delivery_manifest.json`, `final_report.md`, and `gate_4_report.txt` review the final deliverables. |

The run root contains `state/`, `vault/`, `generated/`, `logs/` and `reports/`. Console progress and status display the same workflow-stage names alongside the detailed checkpoint. There are seven workflow stages and four approval gates.

## Reading the shared-library plan

Each planned run exports `reports/2_migration_planning/shared_library_plan.json`. It is an inspection snapshot of the structured plan stored in `state/migration.db`; conversion tools read the database copy. For approval, start with `reports/2_migration_planning/gate_1_report.md` and its linked operation and shared-library reports in `gate_1/`.

A component key combines a type and an inventory ID. Look up `implementation:<id>` in `reports/1_intake_and_legacy_analysis/component_inventory.json` under `implementations` to find its Java class, package and source path. Look up `definition:<id>` under `definitions` to find its configured component kind, name and source location. These IDs preserve the connection to the original component; generated Java uses readable class names.

| Field | How to read it |
| --- | --- |
| `fingerprint` | Identifies this plan's assignments, source/configuration evidence and planning settings. It helps detect changed plans. |
| `libraries` | Proposed shared JAR projects, each containing the fields below. |
| `libraries[].library_id` | The destination library: `common-lib` or a `shared-...` library grouped by its consumers. |
| `libraries[].version` | Planned Maven version, including an identifier derived from the run, components and generation settings. |
| `libraries[].component_keys` | Inventory components whose converted code belongs in this library. |
| `libraries[].consumers` | Combined channel/operation consumers of the library's components. |
| `assignments` | Component-to-destination mapping. A library name places the component in that JAR; `null` keeps it in an operation's project. |
| `consumers` | Per-component lists of distinct legacy channel/operation pairs that use it. Selected operations become generated services; other entries provide workspace-wide sharing context. |
| `usage_counts` | Number of distinct channel/operation consumers per component. Each operation counts once, regardless of repeated calls. This count drives sharing decisions. |
| `reference_counts` | Raw configured uses and discovered Java references, retained as diagnostic detail. |
| `shared_library_min_usage` | Minimum distinct-consumer count for assigning a component to a shared library. |
| `broad_library_usage_threshold` | Components used by more consumers than this threshold go into `common-lib`. |
| `diagnostics` | Detected planning problems requiring investigation, such as ambiguous source identities, dependency cycles or a shared library depending on operation-local code. An empty list means the analysis detected none. |
| `conversion_order` | Dependency-first component order: convert a required component before components that depend on it. Entries use the same inventory keys. |
| `library_dependencies` | For each library, the other generated libraries it requires. An empty list means it has no dependencies on other planned libraries. |
| `library_build_order` | Dependency-first order for building the generated JAR projects. |
| `dependency_analysis` | Describes the analysis scope and its limits. Current evidence comes from static source references; reflection and runtime dispatch require additional review. |

For example, with thresholds of **5** and **10**, a component used by four distinct operations stays operation-local; five through ten consumers place it in a grouped shared library; eleven or more place it in `common-lib`. One operation calling a component a hundred times contributes **one** consumer. The counts cover discovered consumers across the legacy workspace, while the migration's selected scope determines which operations are converted.

To review the plan, trace components to their readable inventory names, check their destinations and consumers, then inspect diagnostics and dependency order. Record your decision through **Approve a gate** or **Reject a gate**, and use **Resume a migration** to continue.

## Run status and current phase

Run state uses two fields with different meanings:

| Field | Meaning | Examples |
| --- | --- | --- |
| `status` | Overall run condition. | `paused`, `in_progress`, `failed`, `blocked`, `completed` |
| `current_phase` | Current checkpoint or activity. | `planning_inputs_ready`, `planning_failed` |

For example, `status=paused` with `current_phase=planning_inputs_ready` means intake completed successfully and the run is ready for migration planning. `status=failed` with `current_phase=planning_failed` means planning was attempted and errored; this checkpoint alone does not identify the cause, and does not imply a credentials problem.

## Replacing Composer through documented behavior

IBM Composer is a closed external product. The migration uses its documented
behavior as the contract for native Java replacements, together with the
organization's XML configuration and application Java source. IBM product source
is not required to describe the behavior the migrated application must preserve.

Define the shared behavior once for the five component types: operations,
operation steps, formats, decorators, and context. Let the converter extract each
component's configuration and application logic from its XML and Java source.
The LLM combines that evidence with the shared behavior to generate native code.
Compilation, focused behavior tests, and review then check the result. Human
clarification is reserved for concrete ambiguities that affect behavior, rather
than documenting every property in advance.

Snapir supplies the shared Composer knowledge from its embedded application-owned
source. Conversion requests also carry the relevant component code, configuration,
relationships, and available dependency APIs. Shared native support implementations
can provide concrete reusable APIs for that behavior; the formatter support library
is currently a feasibility prototype, separate from the active migration pipeline.

After conversion, humans review business outcomes and error paths, validate
integration with databases and external services, and run acceptance tests against
representative legacy inputs and outputs. They resolve any flagged ambiguity using
observed behavior or business requirements, review the generated code, and approve
the migration through its review gates. Compilation is evidence of technical
compatibility; behavior tests and human acceptance establish whether the result
preserves the application's required behavior.

## Migration workflow groups

The workflow can be understood as seven conceptual groups:

1. **Intake and legacy analysis:** inspect the legacy workspace, run the mapper, and prepare planning inputs.
2. **Migration planning and approval gate 1:** create and validate the migration plan, then obtain plan approval.
3. **Dependency closure and component conversion:** resolve operation dependencies and convert the required components.
4. **Component review and approval gate 2:** review converted components, address findings, and obtain component approval.
5. **Operation assembly and review / approval gate 3:** assemble operation implementations, review them, address findings, and obtain operation approval.
6. **Service generation and validation:** generate service projects, build and validate them, and collect validation evidence.
7. **Final validation and approval gate 4:** check final deliverables and validation evidence, then obtain final migration approval.

These groups are a conceptual overview, not an exact fixed database phase enumeration. Each group can involve waiting, blocking, failure, or correction checkpoints as applicable. The database stores `current_phase` as a string, with more specific checkpoints such as `gate_1_pending`, `closures_blocked`, `component_revision`, and `assembly_correction_pending`.

### Configuration defaults and overrides

`source/constants.py` owns migration default values. `PipelineConfiguration` references those
values, copying mutable defaults for each profile. Explicit YAML values override defaults;
lists replace defaults, while `gate_policies` merges individual gate overrides.
Unknown fields and target languages other than Java are rejected.

Paths supplied in YAML are relative to that YAML file. Omitted path defaults are relative
to the Snapir project root, independent of the current directory. The configuration wizard
displays these same defaults relative to `configs/`. Standalone intake resolves explicit
`.env` paths relative to that file and central fallback paths relative to the project root.

Profiles can override model settings, retries, batch size, concurrency, batch delay,
operation filters, library thresholds, Java target/JDK folder, Maven configuration and deployment settings.
Spring Boot 3.5.16 and the supported targets (Java 21 and 25) remain fixed policies. CLI verbose output is a
session option. Credentials come from the process environment named by
`model_api_key_environment`; credential values have no configuration default and are not
copied into profile or database snapshots.

New runs save the complete effective profile and RunConfig. Resume reads those snapshots,
so later default edits do not override saved values. Existing snapshots are not rewritten;
fields absent in older snapshots continue to use model defaults for compatibility.
Generation reuse includes resolved model and Maven settings to reject incompatible output.

Managed conversion uses the installed Maven command and its normal user/global
settings, repositories, credentials, and local cache. Optional `maven_settings_path`
and `maven_local_repository` overrides remain available. The legacy
`approved_maven_repository_urls` setting is accepted for profile compatibility
but no longer restricts repository access.

Dependency closure resolves the operation's mapped Java implementations, including
formatter, decorator, and context tags, and follows their static source dependencies.
Missing superclasses, interfaces, and same-package types block conversion and are
reported with the implementation source and originating configuration. The closure
stores `conversion_components`, the checked inputs and source hashes; conversion
schedules that list rather than discovering extra classes. Changed inputs require
the closure to be refreshed. Static analysis does not prove reflection or runtime dispatch.

External libraries whose source is unavailable can be declared in each migration
configuration. Use an exact `class_name` or a `package_prefix` (matching package
boundaries), and choose `retain` or `replace`. Exact-class rules take precedence;
otherwise the longest matching package prefix wins. Undeclared missing application
classes continue to block conversion. XML-only contexts need no Java mapping, and
`nil` in Composer reference fields means no reference; literal field data is preserved.

```yaml
external_dependencies:
  - package_prefix: com.ibm.dse.base
    treatment: replace
  - class_name: vendor.client.AccountClient
    treatment: retain
    maven_coordinates: vendor:account-client:1.0.0
```

Every managed component-conversion and operation-assembly request includes the
embedded Composer behavior on runtime execution, context, formats and
format/unformat, and decorators. The complete sections live once in
`source/runtime/composer_conversion_knowledge.py`; conversion does not read the manual
file or depend on its headings, structure, or presence. This context is mandatory,
including requests without external dependencies. The application owns this knowledge;
developers configure external classes/packages and their treatments. Third-party
replacements require a `behavior_description` for behavior outside the Composer manual.
Older `behavior_sections` and `composer_behavior_document` fields are accepted for
compatibility, ignored, and omitted from newly saved profiles.

Closure reports record each external class, treatment, usage origin, and documentation
references. Conversion requests receive the required excerpts once each alongside the
source and XML configuration; verbose logs preserve the request for inspection.
Changed evidence invalidates conversion reuse. Retained libraries are resolved by
Maven or the configured classpath; existing checks still prohibit retaining the legacy
Composer runtime itself. The wizard accepts an optional external-rule JSON list
(Enter keeps it empty) and saves it in the run profile.

Each migration may select `java_version` (21 or 25; default 25) and `java_home`
(the installed JDK folder). An omitted folder is discovered locally for the selected
version. Intake saves the resolved version and absolute JDK folder in `state/profile.json`;
resume uses those values. Maven, Java compilation, source analysis, generated POMs,
model instructions, and validation use the selected toolchain without changing Windows
environment variables. The folder must contain a matching JDK with both Java and javac.

```yaml
java_version: 21
java_home: 'C:/Program Files/Java/jdk-21'
```

Create separate configurations and runs to compare Java versions. The Composer mapper
is a separate tool compiled for Java 25 and runs on a discovered Java 25 JDK even when
generated services target Java 21. Check a configuration's toolchain with
`python source/health_check.py --config configs/example.yaml`.

### Configuration value locations

Paths beginning with `state/`, `reports/`, or `logs/` below are relative to the selected run folder.

| Location / source | Types of values defined or stored | Role and persistence |
| --- | --- | --- |
| `source/constants.py` | Central migration defaults: model settings, paths, channels/languages, Java target and JDK folder, filters, retry/concurrency limits, batch delay, gates, library thresholds, Maven and deployment settings. Java defaults to 25; supported targets are 21 and 25. Spring Boot remains pinned to 3.5.16. | Supplies defaults for new profiles; model fields reference these values and copy mutable defaults. Contains no actual credential default. |
| `configs/*.yaml` (or the selected YAML file) | Explicit per-migration overrides, including source/mapper/output paths, scope, model configuration, gate policies, build policy and deployment settings. Credentials are represented only by their environment-variable name. | User-maintained input for new runs. Explicit paths are YAML-file-relative; omitted path defaults are project-root-relative. Actual credentials belong in the process environment. |
| Process environment | Actual model credentials, such as the value of `GOOGLE_API_KEY` or another name selected by `model_api_key_environment`; other SDK/process inputs can also affect the current execution. | Read by the current process. The environment is not copied wholesale into profile or database snapshots, and model credential values are not persisted there. Environment values are not all secrets. |
| CLI arguments | Current command, configuration selection, run ID, gate selection and `--verbose` / `-v`. | Selects the current action. Verbosity is session-only; the selected or generated run ID becomes the persisted run identity, and approval/rejection actions write gate decisions to the database. CLI arguments are not saved wholesale. |
| `state/profile.json` | Complete resolved, validated project profile: defaults plus YAML overrides, resolved paths, model provider/name/endpoint, credential-variable **name**, gate policies, retries, concurrency, library thresholds, Maven policy and deployment settings. | Per-run settings snapshot read on resume. Stores model configuration without the actual model credential. |
| `state/migration.db` | Effective `RunConfig`: run ID/mode, source and derived run paths, channels/languages, filters, model name/endpoint, retries, concurrency, batch size/delay and rerun policy. Also stores artifacts, dependencies, plans, tasks, status/current phase and gate approvals. | Continuation database holding both effective settings and evolving migration state; it is not only a status store. Resume reads the saved `RunConfig` from its run record. |
| `reports/1_intake_and_legacy_analysis/run_config.json` | Inspection copy of the effective `RunConfig` stored in the database. | Human-readable run-settings report; optional for continuation because resume uses the database copy. |
| Other reports, logs and later-stage evidence | Discovery/analysis results, mapper output, gate reports, closures, review findings and validation evidence. | Explain what happened and support approvals; they are distinct from configuration sources. Intake inspection reports are optional for continuation, while later stages can require their gate reports and evidence. |

Some effective settings intentionally overlap between `state/profile.json` and the database's
`RunConfig`: the profile carries project/model/build/deployment policy, while `RunConfig`
provides the effective settings used by run-scoped tools. Resume reads both saved settings
snapshots and obtains model credentials from the current process environment. The CLI still
uses the selected YAML's `output_root` to locate the run; editing that YAML or central defaults
does not replace fields already saved in the run. Older snapshots missing newer fields may
use model defaults for those absent fields; existing snapshots are not rewritten automatically.

### Automatic Composer framework boundaries

`source/constants.py` defines `COMPOSER_FRAMEWORK_PACKAGES`, the central list of
Composer product packages. Extend this list for the Composer packages used in your
organization. Closure checks available application source first, even within these
packages. When source is unavailable, it records matching classes as framework
replacements and supplies the embedded Composer behavior to conversion instead of
requiring proprietary product source. Matching respects package boundaries; missing
application classes, ambiguous references, and changed inputs still block conversion.
Explicit external-dependency rules continue to apply. This classification identifies
replacement work; compilation and behavior review still verify the generated result.
