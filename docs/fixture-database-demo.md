# Fixture database demonstrations

Plan B consumes installed, pinned Plan A tools. Generation does not build/download
server or driver code, regenerate Java, start a demo, or resume conversion.
Operation code, the standalone Java runner and shared Hikari runtime receive
ordinary JDBC settings and have no demo branch.

## Prepare saved references

Assembly creates production `values.yaml` and a separate `demo-values.yaml`
before Gate 3. Converter-only records are stored outside the operation project at
`generated/.converter-demo/<channel>/<operation>/`: `demo-preparation.json`,
`operation-demo-scenarios.json`, `.demo-owned-files.json`, `.demo-scenario-generation/`
and `.demo-scenario-verification/`. Gate 4 still precedes microservice creation;
Gate 5 still reviews the final result. Missing optional demo evidence is unavailable
and does not change conversion acceptance.

```powershell
$env:PYTHONPATH='source'
python source/fixture_demo.py --project <operation> --output-root <generated-root> --operation CHANNEL/Operation
```

Assembly now prepares `operation-demo-scenarios.json` automatically, on both fresh
assembly and cached reuse. AI receives the complete saved native code, verified
original code/configuration and existing fixture banks. It prepares a coherent
normal-path request, resource responses, explicit data links and an expected XML
response before execution. It cannot return or change Java.

The preparation role has its own persistent bounded attempt history under
the external `.demo-scenario-generation/` directory. It does not consume/reset implementation counters or
write the conversion database. Unchanged inputs reuse saved output after validation;
valid saved responses can also be revalidated after a preparation-validator fix.
Source citations must match supplied literal evidence, including selected Composer
XML definitions. XML-fragment responses use the existing boundary comparator.

New fixture data is append-only. Existing JDBC query sets are reused by exact value
identity where possible, with explicit pointer rebinding and a before/after query-set
equality check. SQL, parameters, field names and field casing are not normalized or
repaired. The original model output and the resource-reuse provenance are retained.
User-edited definitions and overlays are preserved. Unchanged generated unavailable
overlays upgrade automatically when preparation succeeds.

To prepare and explicitly verify an existing saved operation without resuming conversion:

```powershell
python source/fixture_demo.py --project <operation> --output-root <generated-root> --operation CHANNEL/Operation --generate-scenarios --profile <saved-profile.json> --state-db <migration.db> --run-id <run-id> --source-root <Composer-root> --verify
```

The database is opened read-only. Credentials come from the configured process
environment, not a profile file. `--verify` retains managed compile, JUnit and package
checks, runs the selected complete XML entry through the prebuilt fixture JDBC tools,
and compares its output against the pre-execution expectation. Replay misses remain
failures even when application code handles them. The declared JDBC execution count
is also checked. Results are written to the external `.demo-scenario-verification/result.json`.
Only the explicitly selected scenario is executed; other prepared scenarios are not
reported as passed. The case limit remains the profile's existing limit (64 in the
GetClientLinksOp run). This is a native fixture test, not Composer/native equivalence.

The generated definition retains explicit whole-operation scenario links:

Fixture references inside the external scenario definition remain relative to the
operation project, not to the definition file. On the next preparation or validation,
legacy records inside an operation are moved without changing their contents.
Conflicting copies or active preparation locks block migration instead of losing
history. Old absolute proposal pointers are resolved at their new location without
resetting attempts or issuing a model call. Runtime bindings, catalogues, tool paths,
fixture payloads, production values and operation Java are not relocated.

```json
{
  "schema_version": "operation-demo-scenarios-v1",
  "operation": "CHANNEL/Operation",
  "selected_scenario": "success",
  "scenarios": [{
    "scenario_id": "success",
    "input_xml": {"asset_root": "src/test/resources/shared-test-assets/<revision>", "manifest_hash": "<sha256>", "fixture_id": "request", "pointer": ""},
    "resources": {"database": [{"asset_root": "src/test/resources/shared-test-assets/<revision>", "manifest_hash": "<sha256>", "fixture_id": "database", "pointer": ""}]},
    "links": []
  }]
}
```

The preparer verifies banks carried by this operation, XML, explicit producer/consumer
links and conflicting SQL/parameter responses. It then runs the prebuilt server's
fixture verifier. It never parses arbitrary JUnit Java, invents joins between
component scenarios, changes casing or creates data. Multiple scenarios require
explicit selection; the current standalone supports one database resource per run.
An absent complete scenario is reported, not guessed from sample-request.xml.

The shared `generated/demo/<channel>/<operation>/catalogue.json` contains references
only. Fixture payloads stay in their original banks. Exact tools are staged once at
`generated/demo-tools/<bundle-id>/`. Existing user bindings/overlays are preserved.
For a deliberate revision change, retain old preparation files for audit and remove
the old generated demo binding/overlay explicitly before preparing replacements.

## Standalone

```bat
run-operation.bat standalone\demo-request.xml --demo
run-operation.bat --demo-stop
```

The batch compiles maintained external helper sources beside the existing launcher.
`demo-request.xml` comes from the selected whole-operation fixture. The existing
normal `sample-request.xml` is preserved. Editing a generated demo request prevents
automatic replacement of that file and is reported in demo preparation.
The existing Maven/JDK requirement remains; no Python/converter checkout or server
rebuild is needed at runtime. The helper verifies every tool file, uses Plan A's
ownership checks, starts only a local server on the URL's port, prepends only its
JDBC driver to the normal classpath, and passes temporary `--config --database demo`
options to the unchanged runner. Demo never reads production runtime credentials.
`--config`/`--database` overrides conflict with `--demo`.

A per-operation lock prevents overlapping launch lifecycles. Temporary settings
are removed. Newly started servers stop by default; reused servers remain until
explicit `--demo-stop`. An unrelated process is never stopped. XML stays on stdout.
`standalone/.demo-runtime/last-run.json` records sticky replay failures even when
application code handles them. `completed` means smoke execution, not equivalence
or saved expected-response verification.

## Separate microservice images

Managed wrappers use Spring Boot ZIP layout/PropertiesLauncher. Separate immutable
contexts under `images/<variant>/<content-hash>/` share identical application JAR
bytes and this command:

```text
java -Dloader.path=/opt/jdbc/ -cp /app/application.jar org.springframework.boot.loader.launch.PropertiesLauncher
```

`image.jdbcDriver` declares the external artifact `path`, `sha256`, `driverClass`.
Paths resolve relative to root values.yaml. Both variants use the fixed image path
`/opt/jdbc/jdbc-driver.jar`; public Java class names are unchanged. New managed
wrapper builds exclude the explicitly externalized driver's verified Maven artifact
from Boot packaging. Native POMs and historical JARs are unchanged. Duplicate classes
and direct vendor API references block replacement. Production rejects fixture
tooling; the server's separate image context contains no fixture dataset.

`image-variants.json` and package receipts bind the common JAR, drivers, base image,
recipes and contexts. Optional unavailable variants carry a reason. Generating a
context does not build, publish or deploy an image.

## Explicit Helm demo overlay

Only `-f values.yaml -f demo-values.yaml` selects demo. The strict typed loader
merges maps recursively, replaces scalars/lists, deletes null keys and rejects
duplicate/unknown keys. Rendered driver, pool and Secret references are checked.
Demo must select its own database and credential Secret reference.

Fill these before deployment:

- `image.repository`/`digest`: separately built demo application image.
- `demoInfrastructure.repository`/`digest`: separately built fixture server image.
- `fixtureClaim`: existing PVC with original fixture banks and reference catalogue.
- `catalogueInContainer`, `fixtureRoots`, `assetRootMap`: explicit read-only mounted
  paths and original-root relocation. These change paths, never fixture IDs.
- `demoInfrastructure.enabled: true` once mounts and pinned references are ready.

The sidecar uses loopback and the JDBC URL's port, a read-only PVC for fixtures,
and an emptyDir for state. Chart-only orchestration is excluded from Spring config.
A Windows source path is not a remote Kubernetes mount. Fixture data and credentials
are never embedded in ConfigMaps or images.

```powershell
python source/deploy_microservice.py --project <validated-service> --values <operation>/values.yaml --demo-values <operation>/demo-values.yaml --build-image
# Publication/deployment require explicit --publish-image / --deploy actions.
```

Pin the base image digest before building. Build the fixture server separately from
`images/fixture-server/<hash>`, using its own repository/digest. Deployment retains
Secret checks, driver checks, Helm lint/template/package, Kubernetes schema checks
and package receipts. No action runs implicitly.

Spring documents external loading and ZIP layout in
[PropertiesLauncher](https://docs.spring.io/spring-boot/3.5/specification/executable-jar/property-launcher.html)
and [Boot packaging](https://docs.spring.io/spring-boot/3.5/maven-plugin/packaging.html).
