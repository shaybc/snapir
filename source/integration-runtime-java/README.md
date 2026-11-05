# Native integration runtime

Import `NativeRuntimeConfiguration` from the generated Spring application. Inject
`NativeRuntimeProperties`, `DatabaseExecution`, and `OperationContextFactory` into
the wrapper adapter. `DatabaseRegistry` is the replaceable external-resource seam
for isolated tests; native operations and steps must remain real.

`DatabaseExecution.execute(name, connection -> ...)` releases connections using
Spring's transaction-aware API. It does not introduce commits, rollbacks or retries.
`inTransaction` is explicit opt-in and requires a source-backed rollback predicate.
Initialization is loaded from JSON with original key casing and deep-copied per call.
Each application/pod owns its own selected pool. Close application context on shutdown.

This JAR supplies infrastructure, not business SQL, formatter behavior or operation
construction. Instantiate each mutable configured step and operation per invocation.
Never log JDBC credentials, complete request payloads, connection URLs or SQL parameter values.
