# Service and Connector Discovery — Implementation Plan

## Goal

Discover the external services used by each configured operation step, resolve their connector configuration, and supply verified database and driver information before the model generates native code. Reuse discoveries across consumers. Ask the user only when a required decision cannot be resolved from workspace evidence and approved dependency policy.

This is an implementation plan, not an implemented feature. It builds on Section 15 of the Composer developer manual and the supplied service, pool and stored-procedure examples.

## Scope and Boundaries

- Extend the Option Two intake, closure, unit evidence, assembly contracts and production wiring path.
- Keep complete-format and configured-op-step conversion requests separate. Do not introduce mandatory file-by-file model analysis or an operation-wide contract request.
- Discover services used by formats/helpers as well as steps when the source dependency graph reaches them.
- Preserve existing ownership thresholds, gates, dependency policy, accepted-artifact integrity checks and immutable reviewed source.
- Add state and schemas compatibly. Do not reset saved runs or silently declare their old evidence complete.
- Do not redesign stage-seven equivalence evidence or deployment-template generation in this change.
- Do not migrate the database technology. The source connector establishes the existing target; an explicit user-authorized target override is a separate decision.

## Existing Infrastructure to Reuse

| Existing area | Reuse | Current gap |
|---|---|---|
| Channel mappings | Import traversal, channel scope, mapping provenance | Explicit service/resource namespaces and loaded-definition provenance |
| XML reader | Encoding-aware parsing, namespace-independent tags, stable selectors, external-entity rejection | Loaded service/connector files, including configured non-XML extensions |
| Java source index and dependency graph | Class identity, source roots, inherited/supporting source availability | Service lookup argument and configuration resolution |
| Eclipse classpath index | Referenced JARs, variables and unresolved containers | Exact driver coordinates/version metadata |
| Dependency verifier | Repository policy, JDK classes, resolved transitive class owners | Binding the verified driver owner to a discovered connection |
| Behavior-unit evidence | Complete configured units and bounded source splitting | Resolved service/resource evidence and provider source closure |
| Compatibility fingerprints | Evidence identity separate from prompt wording | Service/connector and dependency-policy evidence dependencies |
| Operation resources and wiring | Explicit providers, real step beans, offline startup tests | Stable identities, multiple connectors and source transaction ownership |

## Expected files to change:

Paths marked **new** are proposed. Existing files receive only the integration changes described below; no general refactoring is planned.

### Discovery and persistence

- [service_connection.py](C:/GitHub/shaybc/snapir/source/models/service_connection.py) — **new**, typed service, connector, lookup, binding and resolution records.
- [channel_mappings.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/channel_mappings.py) — expose service/resource registry provenance without breaking existing callers.
- [loaded_service_documents.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/loaded_service_documents.py) — **new**, enumerate effective loaded service/connector documents.
- [service_definitions.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/service_definitions.py) — **new**, index instances and connector definitions.
- [java_service_lookups.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/java_service_lookups.py) — **new**, extract bounded static lookup evidence.
- [service_connections.py](C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/service_connections.py) — **new**, resolve step → service → connector relationships.
- [service_connections.py](C:/GitHub/shaybc/snapir/source/tools/state_store_tools/service_connections.py) — **new**, persist discoveries, decisions and affected consumers transactionally.
- [pipeline_runner.py](C:/GitHub/shaybc/snapir/source/runtime/pipeline_runner.py) — invoke discovery after existing source/classpath/component inventory is available.

### Driver dependency resolution

- [driver_metadata.py](C:/GitHub/shaybc/snapir/source/tools/maven_dependency_tools/driver_metadata.py) — **new**, inspect only relevant classpath JAR metadata and verify candidate identities.
- [driver_resolution.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/driver_resolution.py) — **new**, apply known-version and approved-compatible-version selection policy.
- [constants.py](C:/GitHub/shaybc/snapir/source/constants.py) — versioned policy defaults; no arbitrary vendor or unverified universal Java-25 version.

### Closure, conversion and assembly

- [closure_builder_tool.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/closure_builder_tool.py) — include referenced service/helper source and unresolved connector evidence.
- [closure_validator_tool.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/closure_validator_tool.py) — distinguish missing application source, documented proprietary boundaries and unresolved connection decisions.
- [behavior_unit.py](C:/GitHub/shaybc/snapir/source/models/behavior_unit.py) — additive resolved-resource evidence field.
- [behavior_unit_builder.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/behavior_unit_builder.py) — attach only the services/connectors used by that configured unit.
- [behavior_evidence_freshness.py](C:/GitHub/shaybc/snapir/source/tools/conversion_tools/behavior_evidence_freshness.py) — check loaded definitions and mapping inputs relevant to the unit.
- [dependency_context.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/dependency_context.py) — include selected driver coordinates/version/scope alongside existing known dependencies.
- [behavior conversion runner](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/runner.py) — propagate evidence into unit and assembly requests.
- [compatibility.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/compatibility.py) — version the resource requirement and invalidate affected consumers only.
- [operation_resource.py](C:/GitHub/shaybc/snapir/source/models/operation_resource.py) — additive connector identity and ownership references with backward-compatible defaults.
- [operation_resources.py](C:/GitHub/shaybc/snapir/source/runtime/behavior_conversion/operation_resources.py) — reconcile native provider/input contracts with discovered connector and transaction scope.
- [operation_route_tests.py](C:/GitHub/shaybc/snapir/source/agents/behavior_conversion/operation_route_tests.py) — assembly instructions preserve connection identities and ownership.

### Production wiring and questions

- [service generation runner](C:/GitHub/shaybc/snapir/source/runtime/service_generation/runner.py) — supply the authoritative connection map and driver dependencies to initial and correction requests.
- [operation_wiring.py](C:/GitHub/shaybc/snapir/source/runtime/service_generation/operation_wiring.py) — generate providers for the actual resources, retaining real step objects and mocked external resources in startup tests.
- [startup_resources.py](C:/GitHub/shaybc/snapir/source/runtime/service_generation/startup_resources.py) — validate discovered driver/provider choices against deployment wiring.
- [service_connection_questions.py](C:/GitHub/shaybc/snapir/source/runtime/service_connection_questions.py) — **new**, group unresolved decisions and persist reusable answers.
- [workflow_situation.py](C:/GitHub/shaybc/snapir/source/cli/workflow_situation.py) — explain unresolved service/connector decisions and the next action in the console.

### Verification

- [test_service_connector_discovery.py](C:/GitHub/shaybc/snapir/source/tests/test_service_connector_discovery.py) — **new**, loaded definitions, lookups, branches and channel resolution.
- [test_driver_metadata.py](C:/GitHub/shaybc/snapir/source/tests/test_driver_metadata.py) — **new**, JAR metadata, versions, class ownership and compatibility selection.
- [test_service_connection_evidence.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_service_connection_evidence.py) — **new**, payloads, selective invalidation, sharing and last-resort questions.
- [test_operation_wiring.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_operation_wiring.py) — multiple resources and real Spring wiring without external systems.
- [test_startup_resources.py](C:/GitHub/shaybc/snapir/source/tests/runtime/test_startup_resources.py) — declared driver/default settings match discovered evidence.
- Sanitized XML/Java/JAR fixtures under the existing test fixture directories — reproduce the supplied examples without credentials or proprietary binaries.

## 1. Define the Evidence Contract

Add records that keep distinct identities separate:

- **Service definition:** instance ID, XML tag, effective channel, source file/selector, registered implementation, supporting source identities, sanitized attributes and loaded-file provenance.
- **Connector definition:** connector/pool ID, resource kind, database technology, driver class, connection-setting keys, non-secret pool/timeout/transaction attributes and source provenance.
- **Lookup:** caller implementation, source location, expected service type, expression/parameter providing the runtime name, reachable alternatives and the conditions controlling them.
- **Binding:** operation/channel, configured step occurrence, service identity, connector identity, resolution status, evidence references and ownership facts.
- **Driver resolution:** class name, owning JAR hash, coordinates, version, production scope, verification evidence, selection reason and unresolved constraints.
- **Resolution issue:** missing/ambiguous/conflicting/dynamic status, candidates, affected consumers and the exact decision still needed.

Use stable source identities, not class names alone. Keep source facts separate from inferred candidates and user decisions. Never put passwords, tokens or full credential-bearing URLs into model evidence or reports.

## 2. Index Effective Loaded Configuration

1. Resolve the operation's channel and imported configuration using the existing channel machinery.
2. Retain service registry entries by namespace, original file and channel. Avoid confusing a service tag with an identically named format or step tag.
3. Follow the configured definition-file list. Parse loaded connector/service XML even when filenames end in `.tmp` or another configured extension.
4. Index service instances and connector/pool definitions with occurrence selectors. Workspace presence alone does not make a definition active.
5. Apply documented local/import precedence. Preserve duplicates until resolution; never overwrite conflicting definitions silently.
6. Check path bounds and XML safety through existing readers. Missing referenced files become evidence issues.

Build this index once per workspace snapshot. Database, HTTP and other connector kinds use explicit interpretation rules based on registry/source/manual evidence. Do not classify every arbitrary `poolName` attribute as JDBC or infer a proprietary implementation from its name.

## 3. Extract and Resolve Service Usage

Start from each configured unit's implementation and reachable application helper/base classes. Use Java-aware token/syntax handling that ignores comments and distinguishes literals from executable expressions. Reuse existing analysis where it is sufficient; do not treat regex matches as proof of arbitrary Java data flow.

Supported initial resolution cases:

- Direct named `getService(...)` calls.
- Names held in locally resolvable variables or string constants.
- Names read from known configured step parameters.
- Helper methods with bounded, statically resolvable return choices.
- Conditional alternatives such as the supplied regular versus transactional service branch.
- Inherited application service implementations and their initialization methods.

Resolve each candidate using the actual runtime lookup rules, channel scope, instance configuration and expected type. The expected type narrows candidates but does not identify an instance by itself. Do not lowercase identifiers to make inconsistent names match.

For the supplied example, derive:

```text
Configured stored-procedure step
  → spService-dependent service lookup
  → regular or transactional service instance
  → service implementation and inherited helper
  → poolName
  → loaded Oracle connector
  → configured Oracle driver class
```

If configuration fixes the branch, select that branch and retain why. If both branches are reachable, retain both and their conditions. Arbitrary runtime-generated names remain unresolved rather than being guessed.

## 4. Preserve Connection and Transaction Ownership

Determine separately from database identity:

- Who acquires the resource and who releases it.
- Whether a connection is reused across steps within an operation.
- Auto-commit configuration and explicit commit/rollback behavior.
- Regular versus transactional service selection.
- Timeout, retry and failure behavior evidenced by source or documentation.

The supplied regular path releases its connection, while the transactional path leaves it available. Do not translate both into one unconditional per-step close operation. Do not infer process-wide connection sharing from an instance field.

Carry these facts into the native resource contract. Multiple connector identities require distinct provider names/qualifiers and input bindings. A shared stateless step may receive a provider/configuration at runtime; sharing its Java type must not collapse distinct databases or transaction scopes.

## 5. Resolve Driver Artifacts and Versions

Use this order, stopping as soon as a uniquely verified choice is available:

1. Explicit workspace dependency coordinates/version and the effective classpath.
2. The actual referenced JAR containing the configured driver class; inspect embedded Maven metadata and manifest attributes.
3. Correlate that exact artifact with the configured repository and existing dependency metadata. Record evidence quality; a filename or manifest version alone does not prove Maven coordinates.
4. Verify the class exists in the chosen artifact/resolved graph and that version/scopes agree with known dependencies.
5. Evaluate target-Java compatibility using approved compatibility evidence and focused build/runtime checks. Compilation alone does not certify vendor/server compatibility.
6. If replacement is required, select a pinned, verified compatible candidate under the versioned approved policy. Record why the original version was replaced. Do not silently change vendor or required APIs.
7. Ask the user only if required coordinates, licensing/approved availability, conflicting versions or compatibility constraints remain unresolved.

Do not search unrelated cached JARs as though they were the workspace classpath. Do not choose an arbitrary "latest" release or assume Java 25 establishes a particular driver version. Locally supplied proprietary JARs require an approved managed artifact path; never copy binaries into generated output to bypass dependency policy.

## 6. Persist and Attach Unit Evidence

Add dedicated transactional tables for definitions, step bindings, driver resolutions and user decisions. Store sanitized model/report evidence; access original local files only through normal workspace permissions. Store non-secret source identities and hashes sufficient for freshness checks without exporting secret values.

Extend closure to include the reachable application service/helper source. Proprietary framework internals remain documented replacement boundaries, not mandatory missing-source blockers. An unresolved connection choice has its own issue category rather than masquerading as missing Java source.

Each whole-unit payload receives only its relevant `service_connections` records, definition excerpts, supporting source and verified dependencies. Initial and correction requests use the same authoritative evidence. Use existing bounded bundle splitting only when that unit's evidence exceeds the budget; avoid duplicating shared definitions or pulling in unrelated connectors.

Example structured payload fragment:

```json
{
  "service_connections": [{
    "service_id": "transactionStoredProcedureService",
    "connector_id": "transactionPool",
    "resource_kind": "jdbc",
    "database_type": "Oracle",
    "driver_class": "oracle.jdbc.driver.OracleDriver",
    "resolution_status": "resolved",
    "driver_dependency_status": "pending_verification",
    "ownership": {
      "connection_reused": true,
      "transaction_scope_status": "requires_source_reconciliation"
    },
    "evidence_refs": ["service-definition", "connector-definition", "service-implementation"]
  }]
}
```

This example deliberately supplies no invented Maven version or unproven transaction boundary. Fully resolved records add the verified dependency proposal and ownership evidence.

## 7. Initial Prompt and Acceptance Rules

All relevant initial and correction prompts must state these requirements:

- The resolved connection evidence is authoritative; do not select a different database vendor.
- Reuse verified driver coordinates, versions and scopes. Required proprietary APIs must be replaced according to documented behavior, not imported as unavailable framework code.
- Implement business behavior with explicit native collaborators. Preserve conditional service selection and ownership where reachable.
- Use deployment-supplied connection values and the discovered driver policy. Do not invent localhost URLs, credentials, vendor defaults or canned external-service responses.
- Report unresolved evidence explicitly; do not conceal it with generated placeholders that appear complete.

Acceptance validates database/provider identity, dependency consistency and native resource contracts against persisted evidence. A model's assertion that it used Oracle is not proof. Retain existing Java compilation, tests and dependency verification.

## 8. Assembly and Production Wiring

Propagate connector identity through accepted native interfaces into each operation's resource contract. Assemble using accepted APIs without another operation-wide discovery/contract model request.

Generate one appropriately scoped provider per distinct resolved resource. Preserve constructor injection for real steps and the connection acquisition/release boundaries established from source. Generate deployment property bindings and matching driver dependencies; Helm templates pass values into those bindings.

Startup tests supply mocks for external providers before Spring refresh and verify real service/step wiring. They require no live database. Integration checks separately verify actual stored procedures, transaction behavior and driver/server compatibility when that environment is available. Neither successful mocking nor successful packaging proves database equivalence.

## 9. Ask Only as a Last Resort

Before presenting a question:

1. Resolve effective definitions and channel imports.
2. Inspect configured parameters, reachable source and supporting implementations.
3. Inspect the effective classpath/JAR metadata and approved repository evidence.
4. Reuse an existing decision for the same connector identity and unchanged evidence.
5. If needed, use a bounded evidence-only model analysis within the affected unit; require cited source locations and validate its result. Do not allow this fallback to invent runtime configuration.
6. Present a grouped decision only if a required fact is still unresolved.

Group questions by connector or ambiguity, not operation count. Show affected operations, what was found, what is missing and verified choices. Persist answers with the evidence identity and reuse them for all affected consumers. Revisit an answer only when its underlying facts change. Dynamic alternatives that can be implemented safely without one fixed choice do not require a forced selection.

Use the existing human-decision/pause mechanism where possible; the new question helper prepares evidence and grouping rather than adding a second approval system. Console status must identify an unresolved connector and required action clearly.

## 10. Resume and Selective Invalidation

- Prompt wording alone must not invalidate accepted units.
- Service/connector bindings, relevant non-secret configuration, service/helper source, driver selection and versioned semantic requirements are evidence inputs.
- A changed connector invalidates only units using it and their dependent assembly/wiring outputs.
- A changed Java service affects its recorded consumers; an unrelated connector does not affect them.
- Preserve accepted artifacts and response history. Changed transaction ownership may legitimately require affected units to reconvert; do not promise reuse when their behavior contract changes.
- For old runs, build missing discovery state from their recorded inputs, compare new facts with accepted artifacts, and report the impact before regenerating. Do not reinterpret an absent evidence field as a resolved database choice.
- Deployment credentials do not belong in unit fingerprints or prompts. Changing a password alone must not trigger business-code regeneration.

## 11. Verification and Acceptance Criteria

### Discovery tests

- Reproduce service registration, loaded connector/service files, `poolName`, Oracle driver and the supplied conditional lookup.
- Resolve literals, constants, configured parameters, inherited helpers and duplicate service types with distinct IDs.
- Preserve multiple reachable branches and connector identities.
- Verify channel imports/overrides, non-XML loaded filenames, case differences, missing mappings, cycles and dynamic names.
- Confirm unrelated XML and comments do not become active service evidence.
- Verify secret redaction before persistence, prompt serialization and reporting.

### Dependency tests

- Read embedded Maven metadata and manifests from synthetic JAR fixtures containing driver classes.
- Handle conflicting versions, missing coordinates, filename-only hints and unresolved Eclipse containers.
- Verify selected class ownership and production scopes through the existing verifier, including transitives.
- Verify Java-version selection policy; ask only when no approved verified choice remains.

### Pipeline and real-build tests

- Capture initial/correction format and step requests and assert the appropriate connection evidence is present without unrelated services.
- Assert no mandatory per-file or operation-wide contract request is added.
- Exercise two database providers and regular versus transactional ownership paths with controlled resources.
- Run a real Java 25 Spring startup replay offline: real steps/service, mocked external providers, correct bean identities, no driver/server required by the startup test.
- Reproduce the latest invented-vendor/missing-driver behavior and reject it before acceptance when connector evidence contradicts it.
- Hash accepted source and all 15 saved scenario tests before/after disposable replays; no live-run mutation.
- Test selective invalidation, retained history, reuse across operations and one grouped question for shared unresolved resources.

Completion requires that a supplied, fully resolvable service/connector chain reaches the relevant model requests without user questions, while genuinely unresolved facts are reported once with usable evidence. Real database compatibility remains a separate integration result.

## Delivery Sequence

1. Add schemas, persistence and loaded-definition indexing; produce a read-only discovery report.
2. Add Java lookup resolution and connector links; verify the supplied regular/transactional example.
3. Add driver metadata/compatibility resolution and grouped unresolved decisions.
4. Integrate closure and per-unit payloads with selective fingerprints.
5. Integrate native resource contracts, production wiring and acceptance checks.
6. Run disposable end-to-end replays and real Java 25 offline tests before a live-model pilot.

At each step, preserve current approved artifacts and existing pipeline behavior outside the affected service/resource path. Do not mark discovery complete merely because the model can infer a plausible database from a class name.
