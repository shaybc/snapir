# Cross-run component and operation reuse

Approved reusable artifacts live under `shared/`, independently of disposable
`work/` and `outputs/` folders. Set `shared_store_root` to select another durable
location. Explicit paths in a YAML profile resolve against that profile; the
default resolves against the project root. Back up this store with your project
configuration and original source workspace.

## Components

The component-first native converter checks the shared store before requesting
AI implementation. Neutral Java format, decorator and operation-step groups
are eligible. Configured occurrences, routing, format compositions and external
dependency policies keep their existing validation boundaries.

Use the existing native capability selection:

```yaml
conversion_strategy: behavior_units
scoped_native_mode: component_first_v1
source_workspace_id: bank
shared_store_root: ../shared
cross_run_component_reuse: true
```

`source_workspace_id` should remain stable when relocating an application.
Run-local component, source-citation and coverage identifiers are rebound to the
new scope before validation. Generated Java is not rewritten during that process.
Existing `prepare` and `behavior_units_v1` selections are not silently switched
to component-first conversion. The managed-class converter also restores
Gate-2-approved source in later runs, then uses its normal compilation/review
and library-placement path.

Reusable implementations are matched by original source resolution, relevant
entry points, validation policy, target Java version, and native prerequisite
APIs/code. Stronger or different obligations may require another conversion.
An unchanged matching component skips AI generation but still receives current
scope checks and real compilation/tests. Experimental fact-disabled results
are not published for normal cross-run reuse.

The existing global usage thresholds decide whether neutral classes are emitted
locally or consumed through shared JARs. Saving an approved implementation does
not itself change those thresholds. The same JAR revision supplies standalone
and microservice consumers. Incompatible versions of the same shared classes
are rejected rather than silently selected by Maven.

Component publications contain the candidate bundle, converted source, test and
build evidence, a deterministic JAR, its POM, checksums and exact generated
dependency revisions. Publication is atomic and coordinated by an OS-owned
per-component lock. Failed builds cannot publish a reusable result.

## Run records and packaging

The run database records selected revisions in `shared_component_uses`, their
group bindings and their reuse decisions. `dependencies.lock.json` preserves the
selection independently of that database. Existing run/component acceptance
records remain responsible for source freshness and configured-unit approval.

An operation consuming shared JARs receives `shared-dependencies/` containing
only its selected generated dependency closure, immutable component evidence,
and a Maven-layout repository. Its POM uses a relative file repository, so
portable packaging does not depend on the original shared store or preinstalled
generated artifacts. User Maven settings and ordinary third-party repositories
remain in effect. Full offline builds still require third-party dependencies
and build plugins to be available.

The existing portable operation packager copies this directory and verifies
each component's published files and repository JAR/POM. It preserves the
operation POM and sources. External called microservices are not bundled or
started automatically.

## Operations and HTTP endpoints

The default service registry is `shared/operations/registry.db`. Its operation
identities include application, channel and operation. An explicit
`service_registry_path` remains supported. Old registries under
`work/service_registry/` are imported on first initialization without deleting
the original data.

Final approved deliveries retain standalone and optional microservice artifacts
in the operation store. Publishing a callable REST contract still requires the
existing completed workflow, service tests, packaging and gates. Standalone
availability alone does not imply a callable microservice.

API revisions describe the HTTP method, path, wire formats and error policy.
Implementation revisions describe the archived delivery. Runtime hosts are
configuration, and do not participate in the generated caller's API fingerprint.
No deployment-status record is required and publication does not claim that a
service is currently running.

Configure an environment and, where needed, exact target overrides:

```yaml
deployment_environment: test
service_environments:
  test:
    namespace: bank-test
    cluster_domain: cluster.local
    service_port: 8080
    external_url_pattern: https://{service_name}.apps.example.test
deployment_values:
  INTERNET/GetClientLinksOp:
    service_name: internet-getclientlinksop
    namespace: bank-test
    service_port: 8080
    # internal_base_url and external_base_url can override these conventions.
```

The internal service name must match the actual Helm/Kubernetes Service. Newly
generated values explicitly name that Service; legacy charts without a name
retain their existing Helm release-name behavior. Configure `service_name` for
an already deployed target with a different release name. The service port is
the Kubernetes Service port, not an externally exposed Route port.

Standalone callers use the external Route. Their ordinary runtime configuration
contains a `service_urls` map keyed by the registered `operations.*.base-url`
properties. Constructor-injected HTTP clients declare these properties with
Java's `@ConstructorProperties` annotation. Missing bindings fail explicitly.
Demo launchers preserve those service bindings when preparing fixture JDBC
configuration.

OpenShift callers receive internal Service URLs through Helm `serviceUrls` and
the mounted application configuration. They never automatically fall back to
external Routes. Both forms use the same API method, path and wire contracts.
Existing explicit address settings remain supported. Authentication continues
to use runtime configuration/Secret references; the registry does not require
credentials. Availability is exercised by tests or runtime requests, not assumed
from a generated deployment descriptor.

## Recovery and safe deletion

* Deleting `work/` or `outputs/` removes run history and temporary results. New
  conversions can still use `shared/`; deleted runs cannot be resumed.
* Missing analysis caches are rebuilt by the existing analysis paths.
* A missing shared index is rebuilt from complete checksum-verified manifests.
  Interrupted publications can be rediscovered after the artifact directory was
  committed but before its index row was written.
* Missing derived Maven caches are populated from approved JAR/POM publications.
* A missing component JAR with intact approved source evidence can be rebuilt
  through the normal component validator without AI implementation generation.
* A surviving run can restore an exact pinned component publication from its
  verified bundle, compiled classes and retained evidence. Bytes must match the
  pinned manifest; recovery does not silently move an existing run to another
  revision.
* Changed or missing source evidence is not a reusable hit. The affected group
  must be validated/converted again or restored from backup.
* Operation contracts and local artifact references can be recovered from
  complete operation snapshots. Relative references support store relocation.
* A registered remote API can still be called if its local implementation
  package has disappeared. Repackaging that implementation requires its files.
* Losing the entire shared store and all surviving run/package copies requires
  a backup or conversion again. Registries cannot reconstruct lost code from
  operation/class names alone.

Recovery never grants missing approval, invents a deployment, or reconstructs a
deleted run's history. Published snapshots are immutable; changes create new
versions. Do not edit files inside published artifact folders.

## Implementation areas

| Files or package | Why it changed |
| --- | --- |
| `constants.py`, `models/pipeline_configuration.py`, `runtime/configuration.py` | Configure and resolve durable storage independently of run outputs. |
| `.gitignore`, `README.md` | Exclude generated shared data and explain the new workflow. |
| `tools/shared_artifact_store/` | Own immutable manifests, concurrent publication, recoverable indexes, deterministic JARs and portable Maven resolution. |
| `runtime/component_conversion/shared_*.py` | Match neutral implementations, rebind source citations, preserve global usage counts, package shared classes and recover selected revisions. |
| `runtime/component_conversion/requests.py`, `runner.py`, `unit_artifacts.py` | Connect reuse to existing scoped generation and configured-unit validation. |
| `tools/state_store_tools/component_reuse.py` | Record each run's selected component revisions, decisions, consumers and dependency lock. |
| `runtime/shared_libraries/registry.py`, `shared_cache.py` | Restore approved managed-class source through its existing compilation and review flow. |
| `runtime/behavior_conversion/bundle_output.py`, `runner.py` | Attach generated dependencies and materialize portable operation resources. |
| `runtime/operation_reuse/`, `runtime/service_publication.py`, `runtime/finalization/runner.py` | Preserve approved standalone/microservice deliveries and callable contracts outside run folders. |
| `tools/converted_service_registry_tools/` | Relocate registry storage, retain version compatibility, import legacy APIs and recover operation references. |
| `models/converted_service_contract.py`, `service_address.py`, `service_environment.py` | Add implementation revisions and internal/external address information while retaining the existing API-use model. |
| `tools/state_store_tools/service_api_uses.py`, `runtime/operation_coordinator.py`, `tools/operation_call_tools/published_calls.py` | Pin API use without making hosts part of generated-code identity. |
| `runtime/service_addresses.py`, `runtime/behavior_conversion/operation_calls.py` | Resolve execution-specific URLs and require standalone constructor bindings. |
| `models/microservice_deployment.py`, `runtime/service_generation/deployment_configuration.py`, `helm_values.py`, `runner.py`, `packaging_policy.py` | Carry actual Service names, ports and client properties through existing wrapper/package validation. |
| Helm `_helpers.tpl` and `configmap.yaml` | Render stable Service names and internal client URLs. |
| Standalone `StandaloneOperationRunner.java` and `StandaloneLaunch.java` | Inject configured service URLs and preserve them in demo execution. |
| Standalone packager launcher, `StandalonePackage.java`, `PackageSharedDependencies.java` | Include and verify immutable generated dependencies without changing operation source or POM bytes. |
| Focused reuse/recovery/URL/packaging tests and `test_service_registry.py` | Exercise new behavior and retain legacy registry compatibility. |

## Validation

The integration scenario uses real Maven compilation and JUnit execution. Four
runs make one implementation-model call: initial conversion, normal reuse,
recovery after JAR/index deletion, and reuse after source-folder relocation.
Separate checks execute a relocated consumer using only its bundled generated
JAR, exercise standalone HTTP calls, validate Helm output, and recover operation
registries after original run deletion. No live OpenShift deployment was made.

The broader regression selection also exposes existing component-state fixture
failures involving supporting-source folding and cycle expectations. Representative
failures reproduce unchanged against the `before-shared-reg` checkpoint; those
unrelated fixtures and conversion rules were left unchanged.
