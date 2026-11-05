# Standalone operation

New operations use sibling `standalone/` and `microservice/` projects in one repository.
Run the native batches from the repository's standalone project. Run packaging from
its repository root to copy both projects and localize the demo assets. The microservice
is created only after Gate 4 and includes `application`, `integration-runtime` and
`test-support` Maven modules; `mvn clean verify` builds them together without the converter.
Its editable Helm values live inside its chart. Converter records remain outside the repository.


Double-click `package-standalone-operation.bat` to copy this operation project into
`<ProjectFolderName>.PKG`. Move or rename an existing package before packaging again.
The copy retains the original POM, sources, tests, project files, and the exact same
`run-operation.bat`, `run-operation-demo.bat`, and packaging command. It is intended
as the repository where you develop and maintain the operation.

Both locations require the POM's JDK version and Maven. In both, `run-operation.bat`
resolves Maven dependencies, compiles the operation and launcher, then executes it.
There is no prebuilt-only launcher, alternate build POM, or packaged Maven runtime
library cache. Editing the sources affects the next normal build/run.

Packaging localizes the external demo server, separate demo JDBC driver, fixture
banks/catalogue, and runtime settings. It adjusts only those file references in
`standalone/operation.json` and copied microservice values. The demo driver remains
outside production dependencies. User-supplied files and driver JARs already in
this project are retained; dependencies declared in the POM are fetched by Maven.

When the operation's tests use the converter-owned `behavior-verification` helper,
its source project is retained under `standalone/test-support/behavior-verification`.
The same run batch builds/installs it locally before building the operation. This
helper is test-only and is not available from public Maven repositories. After
that preparation, `mvn test` runs the original operation tests normally. The run
batch retains its existing `-DskipTests` behavior; it compiles tests but does not
execute them. Packaging does not disable any converter validation.

`values.yaml` and `demo-values.yaml` remain inputs for later microservice generation.
The converter workflow and Gates 4/5 still apply. Packaging does not generate or
approve a microservice. Build directories, nested `.PKG` outputs, Git history,
demo runtime state, and converter-only preparation records are excluded from the
copy. `.gitignore` excludes build output and local runtime credentials, while
keeping the project sources, demo assets, test-helper sources and values files.

Run from a command prompt with the JDK required by the operation POM and Maven on PATH:

```bat
run-operation.bat "C:\requests\request.xml"
run-operation.bat standalone\sample-request.xml
type request.xml | run-operation.bat -
run-operation.bat request.xml --config "C:\settings\runtime-config.json" --database default
```

`standalone/sample-request.xml` is copied verbatim from a successful request-format test
fixture, preserving the operation's field names and casing. It contains synthetic
identifiers; replace them with identifiers appropriate for your database.
Packaging reports an error if no successful request fixture
is available; it does not publish a negative test as the sample.

The shared config is resolved relative to `standalone/operation.json`, independent
of the caller's working directory. Request paths and `--config` overrides are
relative to the operation folder (or use absolute paths).

Configure `databases.default.jdbc_url`, `ip`, `port`, `schema`, `user`, and
`password`. The URL may contain `{ip}`, `{port}`, and `{schema}` placeholders.
Use the JDBC URL syntax required by your database vendor. Optionally set
`driver_class`; put that vendor's JDBC JAR in `generated/lib/` (shared) or the
operation's `lib/` folder. No database driver or real credentials are bundled.
The `database` field in `standalone/operation.json` selects the named database;
new operations use `default`. Older files without this field also use `default`.
`--database` overrides that selection for one run. Unknown database names fail
rather than falling back to another entry.

The batch builds the project and compiles only the separate launcher sources.
Build/operation diagnostics go to stderr; stdout contains only the XML response.
Nonzero exit status indicates a launcher/connection/execution failure. XML error
responses produced normally by the operation are printed unchanged.

The launcher supports public String-returning `execute` or `process` methods
with `(String, Connection)`, `(String, DataSource)`, or `(String)` parameters,
in that preference order. Dependencies use public no-argument constructors, or
a single unambiguous public constructor recursively. Unsupported APIs or ambiguous
constructors fail rather than guessing values. It does not reconstruct additional
runtime settings or replace the operation's configuration/business logic.

## Optional fixture database demo

```bat
run-operation-demo.bat
run-operation-demo.bat "C:\requests\request.xml"
type request.xml | run-operation-demo.bat -
run-operation.bat standalone\demo-request.xml --demo
run-operation.bat --demo-stop
```

`run-operation-demo.bat` forwards to `run-operation.bat` with `--demo`.
Without arguments it uses `standalone\demo-request.xml`. Supply a request path
or `-` for stdin to override that request. It preserves the runner's exit status.

Demo is available when `standalone/operation.json` has a verified `demo` binding.
Converter preparation reports, scenario definitions, AI history and validation
records are stored outside this operation, under
`generated/.converter-demo/<channel>/<operation>/`. They are not read by the launcher.
A sample request alone
does not link independent component tests into a whole-operation scenario.
Use the XML request retained for the selected scenario.
`standalone/demo-request.xml` is generated from that whole-operation scenario.
`sample-request.xml` remains the separate normal standalone request.

Only the external launcher handles demo. It verifies the prebuilt tools, starts or
reuses the local server on the JDBC URL's port, prepends the separate demo driver,
and supplies ordinary temporary JDBC settings to the unchanged runner. Production
credentials are never read for demo. `--config` and `--database` conflict with demo.
The driver stays outside production `lib` and the operation POM.

Temporary settings are removed. A server started by this invocation is stopped;
a reused server is kept. `--demo-stop` stops only a verified owned server.
Port conflicts never terminate another process. XML stdout stays unchanged.
`standalone/.demo-runtime/last-run.json` records replay failures even when the
operation handles a JDBC exception. Completion is a smoke demonstration, not
proof of equivalence. See the converter's fixture-database-demo guide for details.
