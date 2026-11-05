# Fixture JDBC Tooling Prerequisite Implementation Plan

## Purpose and delivery order

Implement a maintained fixture JDBC server and its matching JDBC driver as part of the converter, before implementing operation demo integration. Build and verify these tools independently of any operation conversion. Install an immutable release in a converter-owned tool store. Later generation only selects, verifies, and copies that release; it never asks AI to generate these tools or compiles a different server/driver for each operation.

This is Plan A. [Plan B: Fixture Database Demo Implementation Plan](fixture_database_demo_implementation_plan.md) consumes its published artifacts and interfaces to integrate standalone launchers, separate production/demo images, PropertiesLauncher, and Helm values. Complete and accept Plan A before implementing Plan B.

This document is planning only. Do not implement, launch a server, rebuild accepted artifacts, run conversion/model requests, reset counters, build images, publish, or deploy while preparing this plan. Keep generated operation logic, saved fixtures, enabled checks, and conversion state unchanged.

## 1. Deliverables and responsibility split

| Deliverable | Owned by this prerequisite | Consumed later by Plan B |
| --- | --- | --- |
| Fixture replay engine | One maintained implementation shared with the existing in-process harness. | Prepared database behaviour behind the demo server. |
| Fixture server | Versioned executable JAR with read-only fixture loading, network execution, lifecycle commands, and diagnostics. | A reusable server process/container launched by external tooling. |
| Fixture JDBC driver | A self-contained JDBC JAR with standard registration and isolated dependencies. | A demo-only classpath entry or the driver in a demo image. |
| Release manifest and tool store | Verified artifacts, versions, protocol/schema support, hashes, entry points, and capability/build evidence. | Pinned tool identities for generation and deployment receipts. |
| Fixture catalogue contract | Schema and generic loading/verification; no operation-specific discovery. | References prepared from accepted operation/scenario bindings. |
| Staging API and tool scripts | Locate a release and copy exact binaries into an isolated destination. | Creation of generated `demo-tools/<bundle-id>` and its binding references. |
| Independent acceptance suite | Plain JDBC, real Hikari, fixture/schema parity, tool-store integrity, and lifecycle tests. | A prevalidated tool release rather than generated infrastructure code. |

Plan A does not change generated operation batches, operation JSON, sample XML, Helm charts, Spring Boot application code, image recipes, approval gates, or conversion acceptance. It defines their future integration contract and demonstrates it in isolated temporary test projects only.

## 2. Existing implementation to reuse

The current `JdbcFixtureProvider` creates in-process `Connection`, `PreparedStatement`, `CallableStatement`, and `ResultSet` proxies backed by explicit query fixtures. Reuse its exact SQL/parameter matching and value semantics. It is not currently a JDBC network server or a registered network driver.

Existing fixture preparation publishes immutable revisions through `runtime.test_assets.store`. Each revision contains a manifest and hash-bound fixture/scenario documents. `runtime.test_assets.references` resolves fixture IDs, strict JSON pointers, and nested `$fixture` references. These are the source of saved mock data; no parallel demo data generator is needed.

Extract only JDBC replay matching and typed result handling from the existing provider. Keep its facade, proxy ownership checks, incomplete tracking, and observable comparison behaviour. Use a shared replay dependency rather than copying a second matcher. Add characterization tests before delegating. Any unrelated defect found during extraction must be separately scoped.

Keep the existing fixture publisher/resolver APIs and stored schema intact. Add a compatible Java read-only implementation of their format, verified against Python golden tests. Do not modify the original fixture files merely to simplify Java loading.

## 3. Maintained source and module layout

Create `source/jdbc-fixture-java/` as a focused Maven reactor:

```text
source/jdbc-fixture-java/
  pom.xml
  fixture-protocol/    # wire messages, typed values, protocol version
  fixture-replay/      # canonical SQL matching and fixture outcome model
  fixture-driver/      # JDBC interfaces and network client
  fixture-server/      # saved-fixture loader, HTTP handlers, CLI, process control
  distribution/       # release manifest, wrappers, assembly descriptors
```

Split classes by purpose: URL parsing, transport, driver registration, each JDBC object family, catalogue reading, immutable asset verification, query matching, connection registry, result encoding, execution journal, and server lifecycle. Thin entry points orchestrate them. Do not accumulate all behaviour in a single driver handler or converter runner.

Use the existing managed JDK/dependency policy. Pin build plugins and dependencies; select no unverified latest version. Record the minimum JRE and verify the repository's current application JDK and Hikari combination. Runtime use of the distributed tools requires Java, not the converter checkout, Python environment, Maven, or an AI API key.

No generated business Java, Composer classes, JavaParser, instrumentation agent, or complete comparison-harness JAR belongs in the driver distribution.

## 4. Build once and publish a converter-owned release

Use an explicit maintenance/build command, proposed as:

```text
python source/fixture_jdbc_tools.py build-release --version <version> --store <converter-tool-store>
python source/fixture_jdbc_tools.py verify-release --store <converter-tool-store> --bundle <bundle-id>
```

The build command uses the maintained sources, runs required tests and managed dependency checks, packages artifacts, then atomically installs a verified release. This is converter-tool preparation, not an operation-generation stage. Do not add an automatic build/download fallback to operation generation.

Proposed default store:

```text
source/resources/fixture-jdbc/
  releases/
    <version>/<bundle-hash>/
      release.json
      jdbc/fixture-jdbc-driver.jar
      server/fixture-server.jar
      bin/fixture-server.bat
      bin/fixture-server.sh
      evidence/build-receipt.json
      evidence/capabilities.json
```

Distribute this store with the converter's installed package. Development builds may populate it explicitly. Binary releases are build/distribution artifacts, not per-operation generated source. Add narrowly scoped ignore rules for local build/store outputs if required; keep maintained source, schemas, wrappers, and release definitions tracked.

`release.json` must declare schema/tool version, protocol major/minor, accepted fixture schemas, bundle identity, minimum JRE, public JDBC class, CLI entry point, artifact paths/sizes/SHA-256 values, dependency/build identities, and capability evidence. Keep fixture payloads and operation identities out of the generic tool release.

Define the bundle hash over a canonical release descriptor excluding its own bundle-hash field, including all executable artifact hashes. No self-referential hash. A release manifest's expected hash must come from the converter's selected release record or another verified installation receipt; accepting an arbitrary self-authored manifest is not integrity verification.

Install through a temporary directory, verify all files, then rename atomically. Concurrent publishers either reuse identical verified contents or fail. Do not mutate an installed release or overwrite different bytes with the same release identity. Updates create a new release; existing operations remain pinned to the old one.

## 5. Driver packaging and classpath isolation

Produce one directly usable `fixture-jdbc-driver.jar`. Include the tool's protocol classes. If the JSON codec requires a dependency, package it under a relocated private tool namespace using a pinned shading configuration. Preserve JDBC service-registration resources. Do not expose ordinary `com.fasterxml.jackson`, Spring, or other application-library classes from that JAR.

Verify the packaged class inventory and JDBC discovery against an application classpath with its own approved Jackson version. The driver goes first in standalone demo mode, so unrelated libraries must not change behaviour due to classpath precedence. Record original dependency coordinates/versions despite relocation; shading is not permission to bypass dependency verification.

The server is independently executable and can package its own verified dependencies. It must not require driver/server dependency JARs to be scattered into production `lib` folders. Keep source-level replay/protocol sharing in the Maven reactor and build the consumer distributions deliberately.

The public class is provisionally `il.co.dcd.fixtures.jdbc.FixtureDriver`. Register it in `META-INF/services/java.sql.Driver` and support explicit `Class.forName` loading used by the current standalone runtime. `connect` returns null for unrelated JDBC schemes; it does not intercept real database URLs. Do not claim full JDBC compliance unless established by the corresponding suite.

## 6. Where database requests and prepared answers come from

The operation's SQL calls are the runtime requests. The fixture server does not receive, unformat, or inspect the operation XML to decide which answer to return. Its inputs are scenario identity, SQL text, bound JDBC parameters, and callable-output registrations.

Prepared answers remain in the converter's existing immutable fixture revisions:

```text
<existing fixture revision>/
  manifest.json
  fixtures.json
  junit-scenarios.json
  comparison-scenarios.json
  validation.json                 # when present
```

An existing database fixture has a `queries` collection. Each entry contains `sql`, ordered logical `parameters`, optional `columns` and `rows`, optional `out_parameters`, and an optional prepared `SQLException`. Preserve the current schema and exact-case identifiers. Do not hardcode GetClientLinksOp, procedure names, table names, fields, result rows, or vendor classes into tooling.

The server reads a reference-only catalogue. Proposed shape, with illustrative paths/hashes:

```json
{
  "schema_version": "fixture-jdbc-catalogue-v1",
  "scenarios": {
    "scenario-success": {
      "resources": {
        "database": {
          "fixtures": [
            {
              "asset_root": "../existing-test-assets/revision",
              "manifest_hash": "<expected-manifest-hash>",
              "fixture_id": "database-success",
              "pointer": ""
            }
          ]
        }
      }
    }
  }
}
```

Allow several existing database-fixture references for one logical resource. Resolve and combine them in memory, never by publishing a copied dataset. Deduplicate identical query definitions; reject conflicting SQL/parameter outcomes or incompatible output registrations. A catalogue may include diagnostic labels and references to the originating scenario, but must not contain a second copy of fixture answers.

Resolve asset paths relative to the catalogue. Support explicit read-only root relocation for a mounted existing store; reject traversal outside allowed roots after path/symlink resolution. Expected hashes remain unchanged after relocation. Missing or unreadable roots are errors, not triggers for AI, regeneration, network discovery, or nearest-match selection.

Follow `store.load` semantics: canonical manifest-object hashing must match Python's existing digest exactly, and document hashes verify original file bytes. Add parity cases for Unicode escaping, object ordering, numeric forms, nulls, CR/LF, and XML text. Do not normalize line endings before hashing. Implement strict JSON-pointer and nested `$fixture` resolution with missing/cyclic reference rejection and the same case sensitivity.

The server freezes a verified catalogue/revision set at startup. No automatic hot reload or modification of saved files in version one. A changed catalogue requires an explicit new server instance/restart under lifecycle ownership rules. Verification of these files is definition integrity, not evidence that an entire operation scenario has executed successfully.

## 7. JDBC URL and connection identity

Use a custom scheme, for example:

```text
jdbc:fixtures://127.0.0.1:15432/scenario-success?resource=database
```

Specify a grammar with an explicit host, valid port, encoded scenario ID, and optional resource ID. Reject ambiguous duplicate parameters and malformed encodings. Default resource selection is allowed only when the scenario declares exactly one resource. Do not guess among several resources.

The public driver class and actual URL are normal external connection settings. The standalone runner and Hikari need no knowledge of demo mode. Renaming the driver file does not alter the configured class name.

Server startup accepts an explicit host/port; launch tooling parses the chosen URL and passes that same port. URL parsing checks the configuration, not whether a business operation is permitted. Auto-start applies only to a local server address. A remote target must already exist or be started by explicit deployment tooling.

At connection open, bind an opaque connection ID to its scenario, resource, verified fixture revision, server identity, and protocol version. Keep JDBC state per connection. URL or normal driver properties may carry an optional diagnostic execution label; generated code must not be changed to propagate a special request context.

## 8. Wire protocol

Use a bounded versioned HTTP/JSON API. A small JDK HTTP server and JDK HTTP client are sufficient for transport; the fixture engine remains independent of HTTP.

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health` | Return tool/protocol/server/catalogue identities and readiness. |
| `POST /v1/connections` | Validate scenario/resource and open a fixture connection. |
| `GET/PUT /v1/connections/{id}/state` | Read/update supported JDBC state. |
| `POST /v1/connections/{id}/execute` | Submit complete prepared/callable executions. |
| `POST /v1/connections/{id}/transaction` | Record explicit commit/rollback. |
| `DELETE /v1/connections/{id}` | Close connection and resources idempotently. |
| `GET /v1/reports/{execution-id}` | Retrieve external diagnostics for an isolated execution/session. |

An execution includes a request ID, connection ID, statement kind, exact SQL, indexed typed input parameters, and indexed declared output registrations. Preserve parameter indices across IN/OUT gaps; do not flatten them in transport. Map them to the existing fixture's logical ordered inputs using explicit tested rules.

Responses contain a typed outcome, returned columns/rows, callable scalar/cursor outputs, and diagnostic identity. Use explicit encodings for null, integer, decimal string, boolean, string, supported date/time values, and cursor results. Do not deserialize arbitrary Java classes or call fixture-supplied code.

Bound request bytes, result bytes/rows, open connections, idle lifetime, and transport timeouts. Reject an oversized result without silently dropping rows. Do not stream partial success in the first version. If large-result support is later needed, version and test that capability separately.

Protocol outcomes must distinguish successful results, prepared SQL exceptions, missing fixture, unsupported capability, invalid request, revision/protocol mismatch, and closed connection. A client-side server/network timeout is distinct from a prepared database failure. Retrying an execution automatically can duplicate events; disable automatic execution retries unless the protocol proves idempotence for the same request ID.

## 9. Replay semantics and driver feature matrix

Record parameter setters locally, including `setNull`, `clearParameters`, and output registrations. Send one execution request rather than one network call per setter/getter. Return bounded result data to a local JDBC ResultSet implementation. Keep close and state changes consistent with the server connection registry.

Initial capabilities include the current harness's prepared SELECT behaviour and callable execution with scalar/cursor outputs. Preserve exact SQL and logical parameter equality, declared output types, row order, column casing, numeric conversion, `wasNull`, cursor position checks, and prepared exceptions. Repeated identical requests return identical fixture data; no process-global queue is consumed.

Document each supported JDBC overload and its behaviour. Unknown business-library methods are not blocked by a call whitelist. Unsupported JDBC capabilities return an explicit `SQLFeatureNotSupportedException` or mapped infrastructure failure; do not supply universal zero/null/false defaults that conceal missing implementation. Updates/batches/generated keys or vendor unwrap APIs require declared fixture semantics before they can be claimed as supported.

Implement standard driver metadata, login/connection timeout behaviour, and connection close/abort rules. Test closed connection/statement/result behaviour and repeatable cleanup. Make underlying statement/result ownership explicit so closing one connection cannot close another's resources.

For Hikari, cover `isValid`, auto-commit, read-only state, transaction isolation, network timeout, applicable catalogue/schema state, pool resets, rollback on return where requested, and close. Confirm the required methods using the repository's actual pinned Hikari tests. These are JDBC lifecycle behaviours, not prepared business queries; a pool validity check must not consume a fixture response.

Commit/rollback record intent and connection state; they do not execute transactional database logic. If a scenario requires stateful writes/visibility across calls, report it as unsupported until explicitly modelled. Do not make a general database-simulation claim.

## 10. Failure tracking, debug mode, and concurrency

Use one server implementation with an optional `--debug` mode, not a different generated debug server. Default diagnostics identify scenario, fixture revision, SQL entry/resource, connection/request IDs, timing, and outcome. Debug mode can add controlled request/response detail for synthetic fixtures. Never log JDBC credentials or include them in health/status/receipts.

Record fixture misses, unsupported capabilities, and transport/protocol failures as sticky execution failures. Throw an appropriate JDBC exception to the application, while retaining the server-side diagnostic even if application code catches it and returns normal XML. A prepared `SQLException` is a different outcome and is not itself an infrastructure failure.

Reports are external artifacts. No generated operation hook, demo-aware servlet filter, or custom shared-runtime branch is allowed. A batch or external HTTP client requests the report after invocation. Use dedicated execution/scenario namespaces where precise correlation is required.

Connection state and fixture resource identity are isolated. Several connections can read immutable fixture data concurrently. Different scenarios do not share response queues or state. Pooled requests may reuse a physical connection, so a connection report alone cannot prove which HTTP request caused each call. Where external isolation cannot establish per-request attribution, report aggregate replay results and that limit rather than inventing request-level verification.

## 11. Server CLI and lifecycle contract

Ship lifecycle commands in the executable server JAR so a copied release is runnable with Java only. Proposed command forms:

```text
java -jar fixture-server.jar verify-fixtures --catalogue <path> --expected-hash <hash>
java -jar fixture-server.jar start --host 127.0.0.1 --port 15432 --catalogue <path> --expected-hash <hash> --state-dir <runtime-state>
java -jar fixture-server.jar ensure --jdbc-url <url> --catalogue <path> --expected-hash <hash> --state-dir <runtime-state>
java -jar fixture-server.jar status --state-dir <runtime-state>
java -jar fixture-server.jar report --state-dir <runtime-state> --execution <id>
java -jar fixture-server.jar stop --state-dir <runtime-state>
```

These are proposed APIs to implement and verify, not commands to run during planning. `start` runs the server in the foreground for a terminal or container. `ensure` starts a background local instance only when required, waits for verified readiness, and returns a machine-readable connection receipt. The shipped `.bat`/`.sh` wrappers resolve their own location and Java executable; they do not rely on the converter checkout or search PATH for a random server JAR.

Runtime state is separate from immutable tools and fixtures. Record PID, process start identity, server instance ID, bound address/port, tool and catalogue hashes, owner token, logs, and status. Reuse a server only if its live health identity agrees with the requested release/catalogue. A listening port or a PID alone is insufficient.

On port conflict, incompatible server, stale PID, or failed readiness, return a concrete error. Do not kill or replace an unrelated process. Stop only a verified owned instance, first gracefully, then use a bounded fallback only for that exact owned process. Concurrent `ensure` calls must serialize startup and return the same compatible instance or a clear conflict. No automatic hot reload.

Redirect background stdout/stderr to known runtime log files and keep CLI machine-readable output separate. Do not open an extra visible Windows console; if a PowerShell wrapper uses `Start-Process`, use `-WindowStyle Hidden`. Quote paths with spaces and retain exit codes. Host/port overrides that disagree with the selected URL are rejected rather than silently winning.

## 12. Tool discovery and exact artifact staging

Add a converter-owned tool lookup/staging API. A future generator supplies a pinned bundle ID and destination; the API locates that release, validates its receipt and every executable hash, checks JRE/protocol compatibility, and copies the complete verified runtime bundle atomically.

Example future command:

```text
python source/fixture_jdbc_tools.py stage --bundle <bundle-id> --destination <generation-root>/demo-tools/<bundle-id>
```

No Maven build, AI call, dependency download, or fixture duplication is permitted on this path. Missing tool releases produce an installation/preparation diagnostic. Do not treat that as proof of a failed operation or silently change the conversion acceptance policy.

Staging produces:

```text
generated/demo-tools/<bundle-id>/
  release.json
  jdbc/fixture-jdbc-driver.jar
  server/fixture-server.jar
  bin/fixture-server.bat
  bin/fixture-server.sh
```

Return a binding record with relative artifact paths, driver class, release/hash identity, protocol/schema compatibility, and public commands. Keep the expected release manifest hash in the consumer's trusted receipt/binding, not inferred from an unverified staged file. Reverify copied bytes. Never overwrite another bundle or place tools in generated production `lib` or an operation's `lib`.

Pin all generated references to the content-addressed bundle. An update does not retarget old operations to `latest`. Source-store removal does not break a completely staged tool copy, but removing the separately referenced fixture data makes the demo unavailable. Do not copy fixtures into the binary bundle to hide that dependency.

## 13. How the later operation batch and images find the tools

Plan B will write an optional demo entry into `standalone/operation.json` using the staging API's returned paths and hashes. It includes the JDBC URL, JDBC class, relative driver/server paths, fixture catalogue location/hash, and tool release identity. This prerequisite defines and tests the binding contract but does not edit operation JSON or generated batch templates yet.

The later batch consumes `--demo`, reads that entry, resolves paths against the operation definition, verifies the pinned tools, and calls the shipped `ensure` command using the port from the JDBC URL. It prepares ordinary temporary runtime settings and invokes the unchanged Java runner with existing `--config`/`--database` options. Only the fixture driver JAR is prepended to the normal classpath; the full server JAR must never enter the application's classpath. Normal mode uses neither tool directory.

The converter copies tools at explicit demo preparation/generation time from its own store. The batch does not recompile or regenerate tools when launched. If its staged tools are absent or altered, it reports the missing/corrupt bundle rather than searching for any JAR or copying unverified binaries from an arbitrary installation.

For Plan B images, the same driver artifact is copied to the demo image's fixed `/opt/jdbc/jdbc-driver.jar`; the production image contains only its real verified driver there. Both use the same application JAR and PropertiesLauncher command. Server artifacts are supplied to the separate fixture-server container/sidecar, not the application JAR. Existing fixture data is mounted read-only. The application remains configured only by normal URL/class/connection settings.

Plan A may provide a maintained container build recipe for the generic server executable, but building/publishing a server image is an explicit action. Per-operation image and Helm changes remain entirely Plan B.

## 14. Tool verification and prerequisite completion

Implement and validate this prerequisite without running the full converter or editing saved operation candidates.

1. **Characterize existing replay behaviour.** Confirm current prepared queries, callable outputs/cursors, nulls, exact-case columns, numeric matching, exceptions, resource closure, and incomplete tracking before extraction. Keep those regressions passing afterwards.
2. **Fixture compatibility.** Build temporary immutable banks through the actual Python publisher; verify Java loading/resolution parity, nested references, duplicate/conflicting definitions, missing fields, changed bytes, cyclic references, Unicode, XML, and line endings. Include invalid catalogue roots and hashes.
3. **Protocol and JDBC.** Exercise registered and explicit driver loading with a plain Java client over a real local port. Verify unrelated URLs, malformed URL/parameters, missing inputs, callable IN/OUT gaps, result getters, closed objects, declared failures, fixture misses, oversized messages, timeouts, and unsupported capabilities. Check no real database fallback exists.
4. **Pool compatibility.** Use actual Hikari with the existing shared database configuration API in an isolated test project. Test startup, validity checks, resets, repeat requests, multiple connections, concurrent scenarios, server loss, reconnect, timeout, and cleanup. No app demo branch or mock pool.
5. **Packaging isolation.** Test the self-contained driver on a classpath with application Jackson/Spring dependencies. Verify service registration, no unrelocated conflicting library classes, minimum JRE, manifest/class identities, pinned dependencies, and driver/server distribution separation.
6. **Lifecycle.** Verify `start`, concurrent `ensure`, compatible reuse, port conflicts, stale PID reuse, mismatched catalogue/release, bounded startup, ownership-checked stop, runtime logs, hidden Windows startup, paths with spaces, and foreground container operation.
7. **Store and staging.** Verify build/test/receipt prerequisites, atomic publication/copy, identical-release reuse, tampered files, wrong expected manifest hash, missing release, no latest-version substitution, and no source compilation/download/model call from lookup or stage.
8. **Generic handoff demonstration.** Stage a bundle into a temporary generated-like tree and invoke it with a small plain JDBC client and existing-format fixture files. Demonstrate request/response selection and inspect the report. Do not change actual operation batches/images/values or run GetClientLinksOp conversion to prove this prerequisite.

Completion requires a tested release installed in the converter store, a verified staged-copy receipt, working CLI examples, supported/unsupported capability documentation, and evidence that existing in-process replay behaviour remains unchanged. Merely building JARs is insufficient.

Only after that completion should Plan B integrate accepted operation fixtures, batches, common application JARs, separate images, PropertiesLauncher, and values overlays. Keep the full conversion stopped until the user authorizes otherwise.

## Expected files to change:

### This planning request only

- [fixture_jdbc_tooling_prerequisite_implementation_plan.md](C:/GitHub/shaybc/snapir/docs/plans/fixture_jdbc_tooling_prerequisite_implementation_plan.md) — add the prerequisite tool implementation/store/handoff design.
- [fixture_database_demo_implementation_plan.md](C:/GitHub/shaybc/snapir/docs/plans/fixture_database_demo_implementation_plan.md) — make integration explicitly depend on the completed prebuilt tooling and remove duplicate ownership of tool implementation/build work.

### Future prerequisite implementation: maintained Java tooling

- [New reactor POM](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/pom.xml) — pinned multi-module tool build.
- [Protocol module](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-protocol/pom.xml) and [protocol sources](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-protocol/src/main/java/il/co/dcd/fixtures/protocol/) — typed wire messages, URL/version contracts, and value encoding.
- [Replay module](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-replay/pom.xml) and [replay sources](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-replay/src/main/java/il/co/dcd/fixtures/replay/) — canonical query matching and fixture outcomes.
- [Driver module](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-driver/pom.xml), [JDBC sources](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-driver/src/main/java/il/co/dcd/fixtures/jdbc/), and [service registration](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-driver/src/main/resources/META-INF/services/java.sql.Driver) — self-contained driver and JDBC interfaces.
- [Server module](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-server/pom.xml) and [server sources](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-server/src/main/java/il/co/dcd/fixtures/server/) — catalogue verification, HTTP handlers, connection state, reports, and lifecycle CLI in focused packages.
- [Distribution definitions and wrappers](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/distribution/) — fixed driver/server distribution layout, release schema, and portable command wrappers.
- [Existing fixture provider](C:/GitHub/shaybc/snapir/source/behavior-verification-java/src/main/java/il/co/dcd/verification/fixtures/JdbcFixtureProvider.java) and [harness POM](C:/GitHub/shaybc/snapir/source/behavior-verification-java/pom.xml) — narrowly delegate matching/value semantics to the shared engine while preserving the facade.

### Future prerequisite implementation: converter tool store and APIs

- [New release model](C:/GitHub/shaybc/snapir/source/models/fixture_jdbc_tool_release.py) — versions, expected hashes, artifact roles, and compatibility evidence.
- [New catalogue model](C:/GitHub/shaybc/snapir/source/models/fixture_demo_catalogue.py) — reference-only scenario/resource schema shared with later integration.
- [New tool management package](C:/GitHub/shaybc/snapir/source/runtime/fixture_jdbc_tools/) — separate modules for explicit building/publication, locating, verifying, and staging releases. Runtime lookup must not call its build flow.
- [New tool command entry point](C:/GitHub/shaybc/snapir/source/fixture_jdbc_tools.py) — thin maintenance `build-release`, `verify-release`, and `stage` CLI.
- [Converter release store](C:/GitHub/shaybc/snapir/source/resources/fixture-jdbc/) — build-populated immutable distributions and a documented installed-converter discovery location.
- [Repository ignore rules](C:/GitHub/shaybc/snapir/.gitignore) — only necessary scoped build/store binary outputs; preserve all unrelated patterns.

### Future prerequisite implementation: tests and documentation

- [Protocol tests](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-protocol/src/test/java/), [replay tests](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-replay/src/test/java/), [driver tests](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-driver/src/test/java/), and [server tests](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/fixture-server/src/test/java/) — unit, real-network, and lifecycle coverage.
- [New tooling tests](C:/GitHub/shaybc/snapir/source/tests/test_fixture_jdbc_tools.py) — release building receipts, integrity, read-only lookup, atomic staging, and generic handoff.
- [New fixture compatibility tests](C:/GitHub/shaybc/snapir/source/tests/test_fixture_jdbc_asset_compatibility.py) — Python-published fixture/reference/hash parity with Java.
- [Existing fixture tests](C:/GitHub/shaybc/snapir/source/tests/test_shared_test_assets.py) — retain and extend only replay regressions needed by the shared engine handoff.
- [New tool guide](C:/GitHub/shaybc/snapir/docs/fixture-jdbc-tools.md) and [tool README](C:/GitHub/shaybc/snapir/source/jdbc-fixture-java/README.md) — install/build/use commands, store layout, protocol, fixture loading, capability limits, and Plan B handoff.

No application logic, generated standalone template, operation JSON, operation POM, runtime-config values, Spring wrapper, Helm template, image, gate, retry counter, or saved fixture is an implementation target of Plan A.

## Reference documentation

- [Java JDBC Driver interface](https://docs.oracle.com/en/java/javase/25/docs/api/java.sql/java/sql/Driver.html) — registration, URL acceptance, and connection behaviour.
- [JDK HTTP server](https://docs.oracle.com/en/java/javase/25/docs/api/jdk.httpserver/com/sun/net/httpserver/HttpServer.html) — a maintained JDK transport option for the standalone fixture process.
- [Maven Shade class relocation](https://maven.apache.org/plugins/maven-shade-plugin/examples/class-relocation.html) — isolating bundled codec dependencies from the application's packages.
- [Existing immutable fixture store](C:/GitHub/shaybc/snapir/source/runtime/test_assets/store.py) and [reference resolver](C:/GitHub/shaybc/snapir/source/runtime/test_assets/references.py) — compatibility contracts the Java loader must preserve.
