# Fixture Database Demo Implementation Plan

## Goal and implementation boundary

Provide a network fixture database that answers normal JDBC calls using the converter's existing saved test data. Support standalone and Spring Boot demonstrations without demo-specific logic in generated operations, the standalone Java runner, the shared database utility, or request handlers.

This document replaces the earlier chat plan. It is a plan only. Do not implement it, resume conversion, run model requests, rebuild saved operations, launch servers, build images, or deploy anything as part of updating this document.

The approved design uses separate production and demo images, the same application JAR and PropertiesLauncher command in both images, configuration-based JDBC driver selection, and a separate standalone demo-driver directory. Existing operation Java, validation policy, retry counters, fixtures, and conversion state remain unchanged.

## Prerequisite and tool ownership

This is Plan B, the operation demo integration plan. First implement and accept [Plan A: Fixture JDBC Tooling Prerequisite Implementation Plan](fixture_jdbc_tooling_prerequisite_implementation_plan.md). Plan A provides a tested server/driver release in the converter-owned immutable tool store, its catalogue/protocol contracts, lifecycle commands, and verified staging API.

Server, driver, replay engine, and generic lifecycle tooling are maintained converter infrastructure implemented up front. Operation generation never generates, rebuilds, downloads, or asks AI to implement them. It only selects a pinned installed release, verifies its manifest, and copies exact tools into `generated/demo-tools/<bundle-id>`. Missing releases produce a preparation diagnostic rather than an automatic build. Fixture data remains referenced from its existing store and is not copied into that tool bundle.

Implement this plan only after the prerequisite tool release is complete. The sections below describe integration requirements and use of that release, not a second implementation of its internals.

## 1. Responsibilities

| Component | Responsibility |
| --- | --- |
| Generated operation and wrapper | Execute the existing logic against standard JDBC interfaces. No demo condition or fixture API. |
| Existing standalone Java runner | Read ordinary database configuration and invoke the operation. No `--demo` parsing or server management. |
| Existing shared database runtime | Supply the configured JDBC URL and driver class to Hikari. No custom reflection or demo branch. |
| Standalone batch and its external helper | Resolve `--demo`, start or reuse the fixture server, prepare ordinary runtime settings, and add the demo driver first on the classpath. |
| Build and deployment tooling | Select the production or demo image and values; start the fixture server when requested. |
| JDBC fixture driver | Implement JDBC and communicate with the fixture server. Accept only its fixture URL scheme. |
| Fixture server | Verify existing fixture references and return prepared results for matching JDBC calls. |

Do not introduce a configurable replacement database-utility class. Only the standard JDBC driver class is selected by configuration. Its fully qualified Java name is unchanged when its JAR file is renamed.

## 2. Reuse existing fixtures without copying their data

Reuse `runtime.test_assets.store.load`, existing fixture references, and the immutable `manifest.json`, `fixtures.json`, `junit-scenarios.json`, and `comparison-scenarios.json` documents. Keep JUnit and comparison scenarios distinct; either can reference the same fixture bank.

Create a shared `generated/demo/catalogue.json` containing references, expected manifest hashes, operation identities, scenario IDs, resource IDs, and preparation status. Do not copy fixture rows, XML documents, comparison reports, or expected responses into a new demo dataset. Do not restore the removed `standalone/sample-request.json` file.

The fixture server loads referenced files read-only. It does not need a writable migration database. Resolve relative paths against the catalogue location and support an explicit fixture-root relocation for read-only container mounts. Relocation changes paths, not fixture identities or expected hashes.

If required files are missing, unreadable, changed, ambiguous, or from another operation, report demo preparation as unavailable. Do not regenerate data, select a different revision silently, or modify the accepted operation.

## 3. Prepare a coherent whole-operation scenario

The current sample XML is selected from a successful request-format comparison. That alone does not establish that database-step and response-format fixtures support the complete operation.

Preparation must:

1. Read accepted operation and component bindings.
2. Locate and verify their current saved fixture receipts.
3. Prefer an explicitly retained whole-operation scenario, when one exists.
4. Otherwise resolve explicitly linked component scenarios and their resource references.
5. Check that the request inputs, stored-procedure parameters/outputs, and later lookup inputs can be used together.
6. Group resource fixtures by their configured logical database binding.
7. Reject conflicting responses for the same SQL and parameters; deduplicate identical entries with provenance.
8. Publish runnable references only after preparation succeeds.

Do not infer fixtures by parsing arbitrary JUnit implementation code, invent joins between unrelated scenarios, change field-name casing, create an input cross-product, or use current native output as a newly invented expected result. If composition cannot be established from saved data, list the unresolved inputs. Preparing new scenarios is a separate decision.

For GetClientLinksOp, explicitly audit the saved procedure call and subsequent table lookups. Do not hardcode those fields, SQL names, or Java classes into the generic preparer.

## 4. Shared replay engine and network server

The replay engine and server are implemented and verified by Plan A. Consume its pinned release without copying their source into generated projects or changing the existing in-process harness during integration.

Pass the prepared reference-only catalogue to the shipped lifecycle CLI. Use its health/readiness, version/revision verification, JDBC execution, connection ownership, and diagnostics contracts. Do not introduce a second SQL matcher, Python server, operation-specific adapter, or server build in this plan.

A missing fixture or unsupported capability remains a replay failure, not an empty successful query. No real database fallback or transactional SQL engine is introduced by integration.

## 5. JDBC driver and connection-pool compatibility

Use the prebuilt self-contained driver from the selected Plan A release and its declared public class, provisionally `il.co.dcd.fixtures.jdbc.FixtureDriver`. It accepts only `jdbc:fixtures:` URLs, for example:

```text
jdbc:fixtures://127.0.0.1:15432/getclientlinks-success
```

Plan A owns JDBC interfaces, typed result handling, prepared/callable execution, closure, isolated codec dependencies, and the actual Hikari compatibility suite. Plan B verifies compatibility of that installed tool release with the selected application/runtime combination and reports missing capabilities; it does not patch the driver for an individual generated operation.

Only the approved driver artifact belongs on the application demo classpath. The full fixture-server or comparison-harness JAR must not be added. Preserve managed dependency and class-shadowing checks, including when the driver comes first on the standalone classpath.

For the first version, a scenario's SQL/parameter responses are deterministic and repeatable. Keep connection state isolated. Do not consume a process-global response queue. Fix the scenario identity for each connection; selecting another scenario requires another database/pool binding or a pool restart.

Distinguish prepared SQL exceptions from transport failures, unsupported capabilities, and fixture misses. Record infrastructure/replay failures server-side even when the operation catches the JDBC exception. External demo tooling checks these diagnostics; no demo-aware filter, request interceptor, thread-local fixture context, or post-invocation hook is added to the application.

## 6. Standalone layout and configuration

Use separate shared tooling folders outside production `generated/lib` and operation `lib`:

```text
generated/
  lib/                              # existing production libraries only
  runtime-config.json               # existing production runtime settings
  demo-tools/
    <bundle-id>/                    # exact copied converter tool release
      release.json
      jdbc/fixture-jdbc-driver.jar   # never part of production lib
      server/fixture-server.jar
      bin/fixture-server.bat
  demo/
    catalogue.json                  # references to existing converter fixtures
  INTERNET/GetClientLinksOp/
    run-operation.bat
    values.yaml
    demo-values.yaml
    standalone/
      operation.json
      sample-request.xml
```

Extend `standalone/operation.json` with an optional `demo` entry consumed only by the batch's external helper. Preserve the existing `service_class`, `runtime_config`, and `database` behaviour. Proposed demo fields are `jdbc_url`, `driver_class`, `driver_jar`, `server_jar`, `fixture_catalogue`, expected catalogue identity, and optional server launch limits. Resolve paths relative to that operation definition. Do not include fixture payloads or real credentials.

Prepare these paths through Plan A's verified staging API, including the pinned bundle/manifest identity in the operation binding. Copy the ready-built tools once per bundle under the generation root and reuse them across operations. The shipped Java lifecycle CLI and wrappers must run without Python, Maven, or the converter checkout; a generated batch never rebuilds or searches for replacement tools.

The URL's explicit port is authoritative. Parse it once and pass that same port to the server; do not maintain an independent conflicting port value. Scenario identity comes from the URL/catalogue, not a guessed request field.

### Launch sequence

The proposed command is:

```bat
run-operation.bat standalone\sample-request.xml --demo
```

The batch and a small maintained external helper will:

1. Consume `--demo`; do not forward it to `StandaloneOperationRunner`.
2. Read and verify the operation's demo entry, catalogue, driver, and server artifacts.
3. Parse the requested server host and port. Auto-start only a local server; a remote address requires an already running server or explicit orchestration.
4. Check server identity, protocol, and fixture revision before reusing it.
5. Start the configured local server if needed, wait for readiness with a bounded timeout, and report a port conflict without killing another process.
6. Materialize an ordinary temporary runtime JSON containing a named demo database entry. Do not overwrite production runtime JSON or copy fixture data.
7. Invoke the unchanged Java runner with its existing `--config <temporary-file> --database <name>` options.
8. Put the verified demo driver JAR first, then the complete existing classpath, including generated production `lib`.
9. Read the external server report and record replay failures without changing the XML produced by the operation.
10. Remove temporary configuration and apply the selected server ownership/lifecycle policy.

Temporary runtime configuration is derived connection settings, not a new fixture store. It must not copy production credentials. If a demo invocation also specifies contradictory `--database` or `--config` overrides, report the conflict rather than guessing precedence.

Without `--demo`, preserve the normal classpath and command options exactly. Never add the demo-driver directory to production `lib`, global `CLASSPATH`, or the operation POM. Diagnostics go to stderr/files; stdout remains the operation XML response.

Use hidden background processes on Windows. Reuse and stop only servers whose identity/ownership is verified. Provide an explicit stop command; do not stop an unrelated process using the same port. Batch quoting must support paths with spaces.

## 7. Two microservice images with one application JAR

Create separate immutable production and demo image variants:

| Item | Production image | Demo image |
| --- | --- | --- |
| Application JAR | Same validated bytes | Same validated bytes |
| Startup command | PropertiesLauncher | Same PropertiesLauncher command |
| Driver path | `/opt/jdbc/jdbc-driver.jar` | `/opt/jdbc/jdbc-driver.jar` |
| Driver artifact | Verified real JDBC driver | Verified fixture JDBC driver |
| Configuration | `values.yaml` | `values.yaml` with explicit `demo-values.yaml` overlay |
| Fixture server | Absent | Separate process/container selected by deployment tooling |

Renaming a complete JAR to `jdbc-driver.jar` is allowed. Do not rename Java packages/classes, rewrite signed JAR contents, or depend on filename-based driver selection. Each configured `driverClass` remains the driver's real public class name.

Both image variants use the following form of startup command, verified against the managed Spring Boot version during implementation:

```dockerfile
ENTRYPOINT ["java", "-Dloader.path=/opt/jdbc/", "-cp", "/app/application.jar", "org.springframework.boot.loader.launch.PropertiesLauncher"]
```

Keep the application main-class information in the normal Spring Boot manifest. The launcher must load both the application/nested libraries and the external JDBC driver. Do not rely on `java -jar` to load an adjacent JAR automatically. No application source implements reflection or checks whether a URL is a fixture URL.

The existing shared pool runtime already passes the configured URL and driver class to Hikari. Continue using that path without a demo branch. Keep credentials as references in production configuration.

### Managed packaging and artifact integrity

Identify driver artifacts through the existing verified dependency/class inventory, not filename patterns. Stage a new common service package whose selected swappable JDBC driver is external, then use that exact application JAR in both images. Do not edit accepted native operation POMs or overwrite historical validated JARs and receipts. Limit changes to managed wrapper/container packaging.

Audit transitive dependencies and direct vendor API references before externalizing a driver. If required vendor classes prevent a clean replacement, report an explicit incompatibility; do not strip dependencies or edit operation Java silently. Do not remove unrelated runtime libraries.

Retain dependency/version checks, external-driver class availability checks, JAR hashes, image digests, package receipts, and provenance for each variant. Update the existing driver availability check so an external verified driver can satisfy it; do not disable it or claim that a filename proves availability. Pin both variants to the same application JAR and base-image digest. Driver/server tools have their own verified identities.

Build the two variants in separate staging directories and image tags. Do not overwrite a production driver's file in a shared mutable workspace to create the demo image. Validate that production image layers contain no fixture driver, fixture-server binary, or fixture dataset.

## 8. Values files and deployment orchestration

Keep production `values.yaml` free of fixture URLs and demo-driver references. Generate `demo-values.yaml` alongside it as a separate, explicit Helm overlay. This overlay is deployment input, not a Spring application profile or business-code mode flag.

The demo overlay selects:

- The separately identified demo image and its digest.
- A named database with the fixture JDBC URL and public driver class.
- Isolated demo credential references if the chart requires credential variables; never production credentials.
- The fixture server image/address/port, catalogue identity, and read-only fixture mount.
- Optional sidecar startup and resource settings consumed only by Helm/deployment tooling.

Do not encode driver binaries or arbitrary executable code in YAML. The demo image already contains its driver at the fixed path. Both images retain the same startup command. The overlay supplies configuration and selects images; it does not copy a production driver out of an image.

Use `helm ... -f values.yaml -f demo-values.yaml` only for an explicit demo deployment. Extend the converter's strict typed values loader to merge and validate that same ordered input, preserve user edits, and bind approval/receipts to the effective merged settings. Helm's merge alone must not bypass converter validation. Reject ambiguous image/driver/configuration combinations.

Keep chart-only orchestration settings out of the rendered application configuration. The ConfigMap supplies ordinary selected database settings; the application does not inspect `demoInfrastructure` or choose a mode. Production credentials continue to use Secret references. Demo overlays must not accidentally inherit the production database's credential reference; create/use a separate demo-only reference through explicit deployment tooling when required.

For Kubernetes, use a fixture-server sidecar or separate fixture service. With a sidecar, the JDBC URL uses localhost and the server port. Existing fixture files must be made available through a configured read-only volume/PVC; a remote cluster cannot mount a Windows path directly. Do not copy datasets into ConfigMaps or the application image. Missing mounts/revisions are reported before claiming readiness.

For Docker/Compose, launch the server as a separate container/process, mount the existing fixture store read-only, and pass normal runtime configuration to the demo application container. Container-network addresses must be explicit; localhost in a separate container does not refer to the server container. Launch/deployment tooling converts the selected values to the already supported Spring configuration mount; Java does not read Helm values directly.

Image creation, publication, server launch, and cluster deployment are explicit actions. Generating Dockerfiles, values files, charts, or catalogues does not perform them.

## 9. Assembly and approval gates

1. Assemble the native operation using the retained checks.
2. Create production `values.yaml`, demo overlay, and reference metadata without a human gate before file creation. Record unavailable demo inputs rather than inventing runnable settings. Preserve edited files on resume.
3. Gate 3 reviews the assembled operation.
4. Gate 4 approves microservice creation using the selected production/demo settings and fixture/tool identities.
5. Generate and validate managed wrapper, packaging recipes, and Helm artifacts for the requested variants.
6. Gate 5 reviews the final generated result and available validation evidence.

Changes to selected driver artifacts, fixture revisions, effective values, or packaging settings invalidate the relevant approval fingerprint. Retain old decisions/history; do not reinterpret them for a different purpose. Do not start conversion or any deployment action from this plan.

## 10. Demo results and assurance

Maintain reports outside operation logic. Record operation/scenario identities, fixture hashes, driver/server versions, readiness, invocation completion, SQL calls observed, expected prepared exceptions, and replay/transport/capability failures.

Use separate outcomes: `unavailable`, `execution_failed`, `completed`, and `verified_against_saved_expectations`. A completed invocation without a saved expected outcome is a smoke demonstration, not a verified behavioural comparison. An operation error XML does not erase server-side fixture misses. Infrastructure failures caught by application code still make the external demo report unsuccessful.

Do not make demo reporting an execution hook inside the standalone Java runner, shared runtime, or HTTP handler. The batch helper or external HTTP demo client owns invocation/report correlation. Scope server connections and reports so repeated/pooled/concurrent requests cannot consume another scenario's data. If reliable per-request correlation is unavailable for a concurrent run, report that limit rather than declaring each request verified.

Existing conversion checks and accepted comparison results retain their meaning. A missing optional demo does not silently change the conversion acceptance policy. Demo success does not establish compatibility with a real database or full equivalence.

## 11. Implementation sequence and acceptance checks

### Required before Phase A

Complete Plan A and verify that its accepted tool release is installed in the converter store. Do not combine prerequisite tool implementation/builds with operation generation.

### Phase A: audit and reference preparation

Audit GetClientLinksOp's saved fixtures and package/dependency inventories. Produce a coherent runnable catalogue entry or specific unresolved items. Prove no fixture payload, operation source, or migration state changed. No model calls or counter resets.

### Phase B: consume the prebuilt tooling

Select and stage the pinned converter release. Verify copied bytes, expected release identity, fixture compatibility, local lifecycle commands, and no build/download/model calls on the generation path. Reuse the prerequisite's tested protocol/driver rather than reimplementing them. A tool capability gap requires a separately maintained tool update, not a manual operation-specific patch.

### Phase C: standalone launch tooling

Verify normal mode's classpath is unchanged and contains no demo-tool paths. Verify `--demo` prepends only the approved driver artifacts, starts/checks the requested local port, translates to existing runner options, and preserves stdout XML. Test quoted paths, missing tools, changed manifests, busy ports, incompatible existing servers, startup timeout, owned-server cleanup, and temporary configuration cleanup. Hash-check the Java runner, RuntimeDatabase, operation source, POM, and saved fixtures before/after.

### Phase D: common Boot JAR and separate images

Validate one common executable application JAR, PropertiesLauncher discovery of external drivers, and configuration-based driver selection. Test both driver artifact variants through the actual Hikari pool. Verify pool validation/reset/close, repeated requests, concurrency, server failure, connection recovery, and explicit fixture diagnostics. Confirm no demo condition or fixture imports entered application code. Compare application-JAR hashes between variants and check production contents for excluded demo artifacts.

### Phase E: values and orchestration

Validate strict base-plus-overlay parsing against Helm's effective configuration. Test production rendering without demo resources, demo rendering with its image/URL/class/Secret references, read-only fixture mounts, readiness, and unchanged initialization keys. Retain Helm lint/template/package, Kubernetes schema, dependency, runtime startup, JUnit, and all other enabled checks. Verify Gate 4 blocks microservice creation until approved and Gate 5 remains final review.

### Phase F: isolated first demonstration

After implementation is separately authorized, use saved GetClientLinksOp Java and existing coherent fixtures for a standalone demo and a microservice HTTP demo. Capture results without regenerating Java or resuming the full conversion. Missing fixture or vendor-API compatibility issues must be reported explicitly. Image build or deployment requires the corresponding explicit action, not merely plan approval.

## Expected files to change:

### This plan update only

- [fixture_database_demo_implementation_plan.md](C:/GitHub/shaybc/snapir/docs/plans/fixture_database_demo_implementation_plan.md) — save the revised architecture and implementation scope. No executable file or generated operation is changed now.
- [fixture_jdbc_tooling_prerequisite_implementation_plan.md](C:/GitHub/shaybc/snapir/docs/plans/fixture_jdbc_tooling_prerequisite_implementation_plan.md) — define the separately implemented converter tools that must be completed first.

### Prebuilt tools supplied by the prerequisite

The [prerequisite plan](fixture_jdbc_tooling_prerequisite_implementation_plan.md#expected-files-to-change) owns maintained Java modules, the existing in-process provider extraction, the reference schema, the converter tool store, release publication, staging, and lifecycle commands. Those files are not reimplemented as part of Plan B generation.

### Future integration: operation references

- [Existing prerequisite catalogue model](C:/GitHub/shaybc/snapir/source/models/fixture_demo_catalogue.py) — consume its validated reference schema; extend only for necessary operation binding metadata.
- [New operation demo preparation package](C:/GitHub/shaybc/snapir/source/runtime/fixture_demo/) — discover accepted operation fixtures, check coherence, call the prerequisite staging API, and produce external demo reports.
- [New demo preparation entry point](C:/GitHub/shaybc/snapir/source/fixture_demo.py) — thin converter-side preparation/report command. Runtime batches use the shipped Java tool CLI, not a Python converter installation.

### Future implementation: standalone generation

- [Standalone generator](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/standalone_runner.py) — preserve ordinary binding fields; add optional demo references and maintained external tooling paths.
- [Standalone batch template](C:/GitHub/shaybc/snapir/source/templates/native_operations/standalone/run-operation.bat) — consume demo options externally and put the isolated driver first only for demo.
- [Standalone README template](C:/GitHub/shaybc/snapir/source/templates/native_operations/standalone/README.md) — explain configuration, tool ownership, fixture references, and normal/demo commands.
- [Assembly values helper](C:/GitHub/shaybc/snapir/source/runtime/operation_assembly/values.py) — prepare demo references and the separate overlay alongside production values without a file-creation gate.
- [Workflow report mapping](C:/GitHub/shaybc/snapir/source/runtime/workflow_stages.py) — locate optional demo preparation/execution reports.

`StandaloneOperationRunner.java`, `RuntimeDatabase.java`, production `runtime-config.json` values, and generated operation Java/POMs are intentionally outside this change scope. The helper translates demo selection to interfaces they already support.

### Future implementation: image packaging and Helm

- [New image-variant/driver artifact models](C:/GitHub/shaybc/snapir/source/models/jdbc_image_variant.py) — typed image variant, verified driver artifact, and shared application-JAR identity.
- [Microservice deployment model](C:/GitHub/shaybc/snapir/source/models/microservice_deployment.py) — backward-compatible orchestration settings without app-level demo behaviour.
- [Helm values loader](C:/GitHub/shaybc/snapir/source/runtime/service_generation/helm_values.py) and [deployment configuration loader](C:/GitHub/shaybc/snapir/source/runtime/service_generation/deployment_configuration.py) — explicit ordered overlay merge, validation, and preservation.
- [Gate 4 handling](C:/GitHub/shaybc/snapir/source/runtime/service_generation/gate.py) — bind selected variants and effective settings to approval.
- [Managed executable packaging](C:/GitHub/shaybc/snapir/source/runtime/service_generation/project_output.py) — externalize only verified swappable driver artifacts in newly staged wrapper packaging, if required by inventory.
- [Microservice output](C:/GitHub/shaybc/snapir/source/runtime/service_generation/microservice_output.py) — retain checks/receipts for common JAR and both variant recipes.
- [New driver staging helper](C:/GitHub/shaybc/snapir/source/runtime/service_deployment/driver_artifacts.py) — verify driver coordinates/classes/hashes and stage the fixed external path.
- [Deployment staging](C:/GitHub/shaybc/snapir/source/runtime/service_deployment/staging.py), [deployment runner](C:/GitHub/shaybc/snapir/source/runtime/service_deployment/runner.py), and [deployment CLI](C:/GitHub/shaybc/snapir/source/deploy_microservice.py) — explicit variant/overlay selection and isolated staging for requested actions.
- [Driver availability check](C:/GitHub/shaybc/snapir/source/runtime/service_deployment/jdbc_driver.py) and [package receipts](C:/GitHub/shaybc/snapir/source/runtime/service_deployment/receipt.py) — verify external drivers and variant provenance without bypassing checks.
- [Helm/container renderer](C:/GitHub/shaybc/snapir/source/tools/deployment_tools/helm_renderer.py) and [Dockerfile template](C:/GitHub/shaybc/snapir/source/templates/microservice/Dockerfile.j2) — separate variant build contexts, identical PropertiesLauncher command, common JAR, fixed driver path.
- [Docker ignore template](C:/GitHub/shaybc/snapir/source/templates/microservice/dockerignore) — keep demo artifacts out of production build inputs.
- [Helm deployment](C:/GitHub/shaybc/snapir/source/templates/helm/native-operation/templates/deployment.yaml) and [ConfigMap](C:/GitHub/shaybc/snapir/source/templates/helm/native-operation/templates/configmap.yaml) — selected image and ordinary database settings; optional fixture-server orchestration confined to the overlay.
- [Helm validation](C:/GitHub/shaybc/snapir/source/tools/deployment_tools/helm_validation.py) — validate the same ordered overlay inputs used for rendering/deployment.

The existing shared integration-runtime Java sources, including `PooledDatabaseRegistry`, remain unchanged unless an independently demonstrated general JDBC defect is separately scoped. Driver loading already belongs to Hikari configuration.

### Future implementation: verification and documentation

- [Prerequisite fixture-tool tests](fixture_jdbc_tooling_prerequisite_implementation_plan.md#14-tool-verification-and-prerequisite-completion) — consume existing release evidence and add application compatibility checks; do not duplicate server/driver implementation tests in operation generation.
- [New demo preparation tests](C:/GitHub/shaybc/snapir/source/tests/test_fixture_demo.py) — read-only reuse, coherence, isolation, integrity, and unavailable cases.
- [Standalone tests](C:/GitHub/shaybc/snapir/source/tests/test_standalone_runner.py) — classpath separation and unchanged runner behaviour.
- [Microservice packaging tests](C:/GitHub/shaybc/snapir/source/tests/test_microservice_packaging.py) and [receipt tests](C:/GitHub/shaybc/snapir/source/tests/test_service_package_receipt.py) — common JAR, driver ownership, variant contents, and external-driver checks.
- [Gate tests](C:/GitHub/shaybc/snapir/source/tests/runtime/test_microservice_gate.py) and [values tests](C:/GitHub/shaybc/snapir/source/tests/test_sequential_gate_values.py) — unchanged gate purposes and explicit overlays.
- [New demo documentation](C:/GitHub/shaybc/snapir/docs/fixture-database-demo.md), [microservice guide](C:/GitHub/shaybc/snapir/docs/native-microservices.md), and [migration guide](C:/GitHub/shaybc/snapir/docs/running_migrations.md) — final implemented commands and operational boundaries.

Generated `demo-values.yaml`, optional `standalone/operation.json` demo entries, shared tool folders, image recipes, and demo reports are future outputs of those maintained generators. Do not hand-edit accepted generated Java or create operation-specific JDBC adapters.

## Source references

- [Spring Boot 3.5 PropertiesLauncher](https://docs.spring.io/spring-boot/3.5/specification/executable-jar/property-launcher.html) — supported external `loader.path` and main-class handling.
- [Spring Boot 3.5 JDBC configuration](https://docs.spring.io/spring-boot/3.5/reference/data/sql.html) — configured driver class and datasource creation.
- [Java 25 DriverManager](https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/DriverManager.html) — standard JDBC driver loading and selection.
- [Helm values files](https://helm.sh/docs/chart_template_guide/values_files/) — user-supplied values and overrides; implementation must verify ordered merge parity against the repository's managed Helm version.
