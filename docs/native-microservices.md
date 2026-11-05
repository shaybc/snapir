# Spring Boot native operation wrappers

Optional fixture database demos, isolated JDBC drivers, separate image contexts
and explicit demo overlays are documented in [Fixture database demonstrations](fixture-database-demo.md).

`microservice.enabled` defaults to `true`. After native operation assembly and
Gate 3 approval, Gate 4 requires approval after the editable root values file is prepared and before shared-runtime builds, wrapper
generation or Helm creation. Gate 4 defaults to `human`, including saved profiles
that specify policies only for Gates 1–3. Explicit `gate_policies: {"4": "automatic"}`
uses the normal automatic approval policy after all preflight checks pass.
Approvals bind to the selected native evidence, deployment configuration and
generation settings; changed inputs require a new approval. Approval alone does
not resume a stopped run. After editing values at a pending Gate 4, use Resume to refresh its report without creating a microservice, then approve Gate 4 and Resume again. Edits after approval require a fresh decision. Use the existing approve/reject and Resume commands.

Gate 5 is the final deliverable review: the sequence is Gate 3 → Gate 4 →
microservice generation/validation → Gate 5. An explicit `microservice.enabled: false`
retains the legacy service-generation path without Gate 4. Accepted operation
Java, POM, source hashes and test fixtures remain unchanged.

Operation assembly seeds `values.yaml` beside the native POM before Gate 3 review, without a separate approval gate. Gate 4 controls microservice creation; Gate 5 approves its final result. This is the editable creation input passed to Gate 4. After approval, microservice creation stages its settings into the chart's `values.yaml`, with local file references adjusted for the service project. Existing edited chart values are not overwritten; changed creation inputs need fresh approval.
Existing definitions and explicit user settings are preserved. Its initial database name comes from the
optional standalone operation definition or `default`; the resulting service
has no runtime dependency on standalone files. Credentials are Secret references,
never copied from standalone runtime JSON into a service, image or chart.
Assembly fills blank `jdbcUrl` and `driverClass` from the operation's uniquely
resolved Composer service-to-pool binding in the effective channel configuration.
It does not guess a pool, vendor, or dependency version. Caller-supplied connections,
ambiguous pools, unresolved substitutions, and URLs with embedded credentials leave
the affected settings unresolved in `operation_values_results.json`. Credentials
remain Kubernetes Secret references; raw configuration and credentials are not
added to model evidence. Existing dependency and deployment checks still apply.
The YAML definition supports comments. Original case-sensitive names and value
types are preserved, and the same typed configuration checks apply to generation
and the deployment CLI. Internal state, receipts and fingerprints retain their
existing serialization.

The generated Spring application imports the versioned native integration runtime.
Each request obtains a fresh mutable operation/step graph, an isolated exact-case
initialization map, and a connection from the selected per-process Hikari pool.
Connection cleanup uses Spring transaction-aware facilities. The default policy
preserves native commit/rollback behavior. Explicit transactions require a
source-backed failure-outcome predicate; the wrapper must not infer one from XML.

The shared runtime is a separately versioned Maven JAR, not code in a parent POM.
The initial supported toolchain is the repository's Java 25 / Spring Boot 3.5.16
and existing approved dependency policy. Converter checks remain enabled.

## Generated service artifacts

Every new operation is a repository under `generated/<channel>/<operation>/`.
Its `standalone/` folder contains the native Maven project and its existing run
batches and standalone helper files. Its sibling `microservice/` is created only
after Gate 4 approval. The microservice root POM builds `integration-runtime/`,
`test-support/`, and `application/` together using `mvn clean verify`. Both private
Maven source projects include their tests, so a different machine needs no
converter-installed private artifacts. The application retains all native sources,
tests and resources plus the Spring Boot wrappers.

The microservice root contains the Dockerfile and `helm/<chart>/values.yaml` and
`demo-values.yaml`. Build the production image from that root after Maven packaging;
the executable JAR is under `application/target/`. Public dependencies still require
Maven repository access. Production credentials remain Secret references.

The operation-root `package-standalone-operation.bat` copies both source projects
and localizes the standalone/demo assets. It excludes build output and converter
working files. Converter receipts, image contexts and schema caches live outside
the operation repository under `generated/.converter-operations/<channel>/<operation>/microservice/`.
Existing legacy flat checkpoints remain readable; explicit byte-verified migration
preserves source files and conversion-attempt history. GetClientLinksOp uses this
sibling layout.
Initialization bindings describe external configuration inputs only, not internal
native call order. Unsupported configured keys must be reported and rejected.

The chart supplies configuration and initialization through a ConfigMap and binds
credentials from an existing Secret. A pool is a Java object in each pod, not a
Kubernetes object shared across pods. Replicas and rolling-update surge multiply
the maximum number of connections. Reconfigure through controlled rollouts.

Packaging runs managed Maven compile/test/package, real Spring wiring tests,
HTTP tests, Helm lint/template/package, and validation against an official pinned
Kubernetes OpenAPI schema (`microservice.kubernetes_version`, initially 1.34.0).
The chart exposes ClusterIP by default; external ingress/authentication is deployment
infrastructure and must not be inferred from native business code.

Readiness/liveness probe application availability. The initial readiness group
does not include a remote database check; business database failures continue
through the operation's accepted error handling. Credentials/configuration must
be supplied before production startup. There is no hot pool replacement.

## Explicit deployment

Complete namespace, image repository/digest, a digest-pinned container base image,
JDBC URL/driver dependency, and existing Secret references. Missing values remain
in `deployment-readiness.json`; successful JAR/chart packaging never claims that
an image exists or that a service has been deployed. JDBC driver artifacts must
be declared in the verified runtime dependency set, not installed into containers
by an ad hoc launch command.
The selected driver class is required for deployment and must exist inside the
validated executable JAR. Packaging can complete while this environment choice
remains unresolved; deployment cannot.

Use the optional CLI only when deployment actions are intended:

```text
python source/deploy_microservice.py --project <service-folder> --values <service-folder>/helm/<chart>/values.yaml --build-image
python source/deploy_microservice.py --project <service-folder> --values <service-folder>/helm/<chart>/values.yaml --publish-image
python source/deploy_microservice.py --project <service-folder> --values <service-folder>/helm/<chart>/values.yaml --deploy
```

Publication returns the registry digest for the candidate tag. Supply that digest
in deployment configuration before installation. Deployment validates the package
receipt, settings, referenced credential keys and rendered chart, then waits for
the Helm release and Kubernetes rollout. It does not create a database or schema.
No action flags means no external build, publication, or cluster action. The deployment CLI passes the namespace from root values to Helm. Manual Helm commands must specify `--namespace` as well as `--values <service-folder>/helm/<chart>/values.yaml`.
Environment-specific Docker/Helm files are staged in converter-owned `deployment-work` using the
current deployment definition and the validated JAR. The original validated
service package is not overwritten by deployment configuration changes.
Image publication verifies the recorded JAR/base-image inputs and local Docker
image identity from the preceding build before pushing its candidate tag.

Chart validation does not establish behavioral equivalence. Native comparator
results and facts-disabled experimental settings retain their original meaning.

Saved pending checkpoints from the earlier swapped Gate 4/5 layout are rejected rather than silently reusing approval for a different purpose. Historical reports and approvals are retained; those checkpoints require explicit migration or a revised run reusing accepted native artifacts.
