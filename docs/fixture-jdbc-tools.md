# Converter Fixture JDBC Tools

The converter owns a maintained fixture server and JDBC driver. They replay saved database fixtures over a network connection. They do not execute SQL against a database or generate business code.

This is Plan A. Operation batch generation, demo operation JSON, image variants and Helm integration belong to Plan B and are not enabled. Conversion can remain stopped while maintaining these tools.

## Build and install

From the repository root, with Java 25, Maven and the converter Python dependencies available:

~~~powershell
python -B source/fixture_jdbc_tools.py build-release --version 1.0.0 --java-home "C:/Program Files/Java/jdk-25.0.3"
~~~

Optional `--maven-settings`, `--maven-repository`, `--store` and `--work` select maintenance locations. Version must match the maintained reactor. An existing build workspace is never overwritten; select a fresh work directory for another explicit build.

The command copies maintained sources, runs Maven/JUnit and Python acceptance, checks dependency policy and class isolation, builds a copy of the original fixture harness for facade regression, and installs only passing distributions. It does not overwrite the analysis JAR used by saved conversions.

The result includes pinned `bundle_id`, `manifest_hash`, release location and build evidence. There is no automatic `latest` selection.

~~~text
source/resources/fixture-jdbc/
  installations/<bundle-id>.json
  releases/1.0.0/<bundle-id>/
    release.json
    jdbc/fixture-jdbc-driver.jar
    server/fixture-server.jar
    bin/fixture-server.bat
    bin/fixture-server.sh
    evidence/
~~~

Include the selected release and installation receipt when distributing the converter. Build-populated binary directories are ignored by Git; maintained source and distribution definitions are tracked. Updates create another immutable bundle and do not retarget existing bindings.

~~~text
python -B source/fixture_jdbc_tools.py verify-release --bundle <bundle-id>
python -B source/fixture_jdbc_tools.py stage --bundle <bundle-id> --destination <output>/demo-tools/<bundle-id>
~~~

Lookup/staging do not compile, download, launch a server, or call AI. They verify every file against the pinned installation and manifest, copy atomically, verify the destination, and return driver/server paths and hashes. Missing/corrupt tools produce an error.

Copied tools run with Java alone: no Python, Maven, converter checkout or API key. Keep them outside production `lib`. Staging never copies fixture data.

## Existing fixture references

Create a reference-only catalogue pointing to a published bank revision:

~~~json
{
  "schema_version": "fixture-jdbc-catalogue-v1",
  "scenarios": {
    "success": {
      "resources": {
        "database": {
          "fixtures": [{
            "asset_root": "../existing-test-assets/revision",
            "manifest_hash": "<expected manifest hash from its receipt>",
            "fixture_id": "saved-database-fixture",
            "pointer": ""
          }]
        }
      }
    }
  }
}
~~~

The server verifies the canonical manifest-object hash and exact document byte hashes, including both scenario documents. It resolves strict JSON pointers and nested `$fixture` references and preserves field/column case, nulls, XML and line endings. Missing, cyclic, conflicting, changed or inaccessible evidence is rejected.

Database fixtures contain explicit SQL, ordered logical inputs, rows/columns, callable outputs or prepared SQL exceptions. References may combine one resource in memory; duplicate definitions are deduplicated and conflicting outcomes fail. No response payload is copied into a catalogue.

Use `runtime.fixture_jdbc_tools.releases.digest` on parsed catalogue JSON for its expected hash; do not hash pretty-printed bytes. `FixtureDemoCatalogue` is the typed preparation model. Whole-operation fixture coherence is a separate Plan B responsibility.

## Server commands

Use the copied server JAR or the wrappers beside it:

~~~text
java -jar <server.jar> verify-fixtures --catalogue <catalogue.json> --expected-hash <hash> --fixture-root <allowed-root>

java -jar <server.jar> start --host 127.0.0.1 --port 15432 --catalogue <catalogue.json> --expected-hash <hash> --fixture-root <allowed-root> --state-dir <runtime-state>

java -jar <server.jar> ensure --jdbc-url "jdbc:fixtures://127.0.0.1:15432/success?resource=database&execution=sample" --catalogue <catalogue.json> --expected-hash <hash> --fixture-root <allowed-root> --state-dir <runtime-state>

java -jar <server.jar> status --state-dir <runtime-state>
java -jar <server.jar> report --state-dir <runtime-state> --execution sample
java -jar <server.jar> stop --state-dir <runtime-state>
java -jar <server.jar> capabilities
~~~

`start` runs foreground, suitable for a terminal/container. `ensure` starts or reuses a compatible owned local process and waits for readiness. The URL port is authoritative. `--startup-timeout-ms` bounds the wait. Remote targets cannot be auto-started locally.

Repeat `--fixture-root` for allowed read-only roots. Explicit relocation is supported with `--asset-root-map "X:/old-fixture-volume=/mounted/fixtures"`. Only the longest declared path prefix is substituted; no filesystem or field-name search occurs. Targets still require allowed-root verification. Catalogue and fixture hashes remain unchanged.

The server freezes verified fixtures at startup. There is no automatic hot reload. Ownership checks bind PID/start time, server instance, tool JAR hash, catalogue hash, host and port. Incompatible servers, occupied ports, forged/stale state and startup failures are errors. An unrelated process is never stopped.

The copied Java lifecycle commands and wrappers resolve their own JAR. Background output is redirected to `server.log`; runtime state stays outside immutable stores. Paths with spaces are supported.

## Normal JDBC connection

~~~text
URL: jdbc:fixtures://127.0.0.1:15432/success?resource=database&execution=sample
Driver: il.co.dcd.fixtures.jdbc.FixtureDriver
~~~

Put only `jdbc/fixture-jdbc-driver.jar` on the application's classpath. It supports JDBC service discovery and explicit `Class.forName`. Never add the whole server JAR. Its codec packages are relocated, so it can precede application libraries without replacing application Jackson.

The application and Hikari use normal URL/class settings. No demo branch, custom reflection, special filter or fixture hook is needed. Future standalone integration will let the batch call `ensure` and pass ordinary database configuration to the unchanged Java runner. That integration is not implemented here.

## Initial JDBC capabilities

| Area | Supported behaviour |
| --- | --- |
| Driver | Fixture scheme only; discovery; explicit class loading; connection/read timeouts. |
| Connection | Prepared/callable statements; validity/closed state; auto-commit, read-only, isolation, catalog/schema/network timeout; transaction intent recording; close. |
| Parameters | Simple indexed string, integer, long, boolean, object, decimal, date/time/timestamp and null setters; clear parameters. |
| Prepared calls | `executeQuery()` and `execute()` using explicit query fixtures. |
| Callable calls | `execute()`, indexed integer JDBC output types, scalar string/object and cursor outputs. |
| Results | Forward-only iteration, exact-name/index getters, null state, numeric/date/binary getters, closure. |
| Pool lifecycle | Actual Hikari validity, reset, return, server failure and cleanup paths. |
| Metadata | Explicit tool/driver identity and supported interface version; no full JDBC compliance claim. |

Exact SQL, ordered input values and output registrations determine matching. No SQL normalization, field-case repair, real SQL execution, stateful writes, batches, vendor unwrap or real transaction simulation is provided. Unsupported JDBC methods fail explicitly; this is not a whitelist of application business methods.

## Reports and debug server mode

Add `--debug` to `start` or `ensure` for synthetic request/response traces. There is one maintained server, not a separately generated debug implementation. Health/status/receipts omit JDBC credentials and the local stop ownership token.

Prepared SQL exceptions use SQL state `FXPRE`. Missing fixtures use `FXMIS`. Unsupported capabilities use `SQLFeatureNotSupportedException`/`FXCAP`; other protocol/replay failures use `FXERR`; transport failures use `08006`.

Expected prepared exceptions do not mark infrastructure failure. Fixture misses and unsupported capabilities remain sticky even if application code catches the exception. Reports persist under `reports/<server-instance>/<execution>.json` and are readable after orderly stop. External tooling inspects them; the operation remains unaware.

Execution labels belong to connection/URL scope. Pooled HTTP requests may share a report. It does not automatically establish per-HTTP-request attribution; use external isolation or report aggregate evidence accurately.

Limits reject work rather than truncate successful data: 8 MiB JSON messages, 32 MiB resolved catalogue data, 512 fixture references, 64 simultaneous connections, 10-minute idle expiry, 15-second server request deadlines, 1,024 execution labels and 10,000 journal events.

## Validation boundary

Release acceptance uses the actual Python fixture publisher, independent Java loading, real local network calls, the shaded driver, the existing facade, actual Hikari and unchanged shared registry sources, evidence/tamper checks, and owned lifecycle/concurrency tests.

No saved operation is converted and no generated batch, image, values file or Helm chart is changed. See the [prerequisite plan](plans/fixture_jdbc_tooling_prerequisite_implementation_plan.md) and [later integration plan](plans/fixture_database_demo_implementation_plan.md).
