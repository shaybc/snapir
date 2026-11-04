# Standalone operation

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
