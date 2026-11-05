# Converter Fixture JDBC Tooling

Maintained Plan A tooling: a reusable server, a registered JDBC driver, and the
exact replay semantics shared with the existing converter fixture harness.
These tools are built and released before operation generation uses them.

Modules:

- `fixture-protocol`: bounded JSON, strict URL parsing, typed transport.
- `fixture-replay`: dependency-free matching/getters. Canonical `Replay.java`
  lives in the sibling `behavior-verification-java` source tree so that the
  existing standalone harness still builds without a new Maven dependency.
- `fixture-driver`: JDBC objects and HTTP client, with relocated codec packages.
- `fixture-server`: verified asset references, HTTP service, diagnostics, Java
  lifecycle commands, plain JDBC/Hikari acceptance.
- `distribution`: maintained Java-only launch wrappers.

Build a tested release from isolated copied sources:

~~~text
python -B source/fixture_jdbc_tools.py build-release --version 1.0.0 --java-home <Java-25-JDK>
~~~

Use the printed bundle ID with `verify-release` or `stage`. These commands never
compile/download/generate tools. Keep their copied artifacts outside production
`lib` and leave fixture data in its existing immutable store.

For Java module development only:

~~~text
mvn --batch-mode -f source/jdbc-fixture-java/pom.xml verify
~~~

The reactor expects the canonical sibling harness source. The maintenance
command also runs Python compatibility and release/lifecycle tests.
No operation, model, or conversion process is started.

See [the tool guide](../../docs/fixture-jdbc-tools.md) for store layout, commands,
reference schemas, capabilities and limits. Plan B batch/image/Helm integration
is intentionally absent.
