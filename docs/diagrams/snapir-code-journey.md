# From Composer source to a maintainable microservice

This is the code journey. The separate system architecture diagram describes
the participating applications, tools and stores.

1. **Composer source.** Start with the selected operations and their original
   XML, Java implementations, libraries and classpath. Selection defines the
   roots; it does not limit discovery to dependencies the user already knows.
2. **AST analysis and Composer mapping.** Parse source structure and XML
   relationships, or reuse a compatible existing indexed map. Verify source
   fingerprints and retain reusable analysis.
3. **Dependency collection and reuse.** Expand the transitive dependency graph
   across projects. Identify required formats, operation steps, classes and
   operation calls. Consult shared component artifacts and registered operation
   HTTP contracts before generating missing code.
4. **Low-level native conversion.** Work in dependency order. Reuse compatible
   converted components and convert missing base formats, OpStep implementations
   and configured units into native Java. Preserve typed APIs and configuration
   semantics. Some formats/steps require multiple internal conversion layers;
   this stage summarizes those layers.
5. **Component validation.** Compile the generated Java and execute AI-generated
   JUnit tests with mocks for external boundaries. Exercise the component's
   behavior rather than replacing it with a mock. Format comparison uses shared
   fixtures and observed original/native XML behavior where applicable. Accepted
   reusable artifacts become available to later work and future runs.
6. **Operation assembly.** Compose accepted components into the operation's
   routing, data flow, initialization and error handling. Calls to other
   operations use their registered HTTP API contracts; they are not silently
   embedded as local operation implementations.
7. **Operation validation.** Compile and execute operation-level JUnit and route
   tests. Mock external services, databases and called-operation APIs. Retain
   validated XML samples and execution evidence. Component tests alone do not
   establish that the assembled operation behaves correctly.
8. **Microservice generation.** Wrap the accepted native business code with the
   Spring Boot HTTP interface. Generate editable runtime/deployment settings,
   build the executable service JAR, execute required checks and validate Helm
   output. This creates deployment artifacts; it does not deploy them.
9. **Portable, maintainable delivery.** Retain Java/Maven source, tests,
   dependency artifacts, configuration, launchers, deployment files and relevant
   documentation. Produce the standalone and microservice deliverables. The
   delivered project can be developed and maintained outside the converter.

The implementation interleaves generation, validation and reuse; each accepted
component is checked before dependent work consumes it. The diagram shows the
logical checkpoints rather than every internal model call or build.

SQLite tracks progress, approvals, attempts and evidence throughout. A failed
check returns diagnostics to the appropriate implementation or test stage;
it is not treated as a successful conversion. Existing shared candidates are
still validated in the current context.

Formal fact collection and validation remain disabled. AST analysis, dependency
resolution, source freshness checks, API/settings checks, compilation and
executed tests remain enabled. Observed test cases do not prove exhaustive
behavioral equivalence.

Standalone HTTP clients use external addresses. Microservice clients use
internal OpenShift Service addresses. Called operation services are assumed
available; the user handles image publication and deployment.
