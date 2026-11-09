# Open issues

## 1. Identify dependency JARs and exact versions, and supply relevant conversion context

Intake currently identifies class availability and the JAR or Java runtime that
provides each class. It does not reliably establish Maven coordinates and exact
versions for every external JAR.

- Discover all dependency JARs from Maven, Eclipse classpaths, configured libraries,
  and resolved project dependencies.
- Determine exact artifact versions and Maven coordinates where available, recording
  their provenance. Investigate resolved Maven metadata, embedded `pom.properties`,
  and JAR manifests; report unresolved or conflicting identities explicitly.
- Map source classes to the external classes and artifacts they actually depend on.
- Design how to supply each relevant source conversion request with its dependency
  identities, exact versions, and useful API/documentation context, avoiding unrelated
  libraries and repeated context.
- Verify generated code against those identified dependencies through compilation
  and appropriate tests.

## 2. Log the source file before processing it

Implemented locally and covered by mapper regression tests.

Before processing each source file or rendering each mapper inventory definition,
write a message to both the console and the corresponding log file. Include the
source file's full path and the current processing phase. For inventory definitions,
also include the definition name and XML selector when available.

- Write the message before starting the work, not only after completion or at
  sampled progress intervals.
- Ensure the message is flushed so it remains available if processing crashes.
- After a crash, the last start message should identify the file and definition
  being processed immediately before the failure.

Indexed mapping also saves a completed source-index checkpoint before rendering.
Recovery through `--resume-analysis` validates that checkpoint and restarts rendering
in a fresh destination; stale or damaged checkpoints require rebuilding the index.
See [mapper recovery instructions](docs/composer_analysis_store.md).

## 3. Default migration readiness and progress fixes

Implemented locally and verified. This change does not extend crash recovery.

Verification: the broad regression run passed 192 tests; its one stale test-helper
patch was corrected and passed on focused rerun (193 tests total). The additional
native routing integration passed using real offline Maven compilation and JUnit.
That numeric fixture isolates portable XML sample generation; production packaging
validation was not relaxed. Reports are saved under `work/default-flow-fixes-regressions.xml`,
`work/default-flow-reuse-recheck.xml` and `work/default-flow-routing-java.xml`.

- Preserve implementation-free fallback opSteps as control-flow occurrences. Never
  infer terminal behavior from the label `OperationFailed`, invent an implementation,
  or skip unsupported processing configuration.
- Resolve Eclipse workspace library paths under the workspace's declared project,
  retaining project-relative, explicit drive and UNC path semantics.
- Apply selected project/dependency classpaths at preparation and downstream proof
  checks. Unrelated projects' classpath errors do not block selected operations.
- Support explicit Eclipse container-to-JAR bindings and configured WebSphere
  runtime discovery. Required unresolved variables, containers and libraries remain
  actionable blockers with project/reference provenance.
- Continue full native profiles from successful intake into the existing gated
  workflow. Preserve prepare-only profiles, genuine blockers and human approvals.
- Report actual preparation blockers, avoid claiming planning finished without a
  saved plan, and distinguish prepared inputs from accepted native conversion.
- Keep preparation, map verification and report writing visible; report-writing
  stack snapshots no longer retain the preceding operation's phase label.

Implementation areas and reasons:

| Area | Files and purpose |
| --- | --- |
| Step semantics | `scoped_closure/step_semantics.py`, `builder.py`, `routing.py`, `models/scoped_step_occurrence.py`: classify and retain structural routing. |
| Unit and assembly evidence | `scoped_workflow/units.py`, `payloads.py`, `component_graph.py`, `runtime/scoped_native/payloads.py`, `runtime/component_conversion/steps.py`, `unit_provider.py`: omit business units only for proven routing nodes and retain implementation bindings for processing steps. |
| Classpath discovery | `source_discovery_tools/classpath.py`, `classpath_scope.py`, `eclipse_library_paths.py`, `eclipse_containers.py`, `models/classpath_issue.py`, `java_classpath_index.py`: resolve paths, containers, selected scope and diagnostic provenance. |
| Configuration | `pipeline_configuration.py`, `runtime/configuration.py`, `java_toolchain.py`, `cli/default_configuration_flow.py`: accept, resolve and scope explicit container library inputs. |
| Consistent freshness checks | `scoped_workflow/preparation.py`, `connections.py`, `scoped_closure/java_origins.py`, `scoped_reuse/fingerprints.py`, `runtime/scoped_native/runner.py`, `scope.py`, `results.py`, `plan_approval.py`, `service_connection_questions.py`, `behavior_conversion/service_connection_evidence.py`, `service_connection_freshness.py`: reuse one classpath selection policy without weakening evidence checks. |
| Startup and continuation | `runtime/migration_start.py`, `pipeline_runner.py`, `checkpoints.py`, `cli/main.py`, `discovery.py`: continue full migrations once, retain real gates and expose prepared checkpoints. |
| Diagnostics and progress | `runtime/scoped_conversion.py`, `scoped_diagnostics.py`, `preparation_progress.py`, `inventory_work.py`, `intake_progress.py`, `inventory_reports.py`, `indexed_intake.py`, `cli/workflow_progress.py`, `workflow_situation.py`, `workflow_subsections.py`: show the actual current work, saved evidence and blocker. |
| Verification | Classpath, routing-only, continuation, startup, scoped workflow/safety, progress, configuration and real Maven/JUnit routing tests. |

Source XML, normal processing implementations, AI test/fact policy, registry storage
and production portable/microservice packaging validation are unchanged. The
enterprise workspace still requires a saved-run retry with its actual required
runtime/variable bindings. See [CLI configuration details](CLI%20Configuration%20Map.md).
