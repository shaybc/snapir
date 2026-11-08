# Snapir component architecture

This diagram shows the **components that participate in conversion and their
interactions**. It is a component/context view, not a sequence diagram. Boxes
represent logical code modules, stores, or external systems; they are not all
independently deployed services.

- [PNG image](snapir-component-architecture.png)
- [Scalable SVG](snapir-component-architecture.svg)
- [Editable draw.io diagram](snapir-component-architecture.drawio)

The images are static. The draw.io master preserves editable components and
stable IDs. Drill-down pages can be created later by referring to these IDs.
These IDs belong to this component view; the earlier workflow overview has its
own numbering.

## Components available for drill-down

| ID | Component | Responsibility |
| --- | --- | --- |
| A01 | CLI & configuration wizard | Collect configuration and scope; accept start, resume and gate commands. |
| A02 | Workspace intake | Discover projects, Java/XML and classpath; prepare and verify source evidence. |
| A03 | Composer XML Mapper | Analyze Composer XML and related Java AST; produce or reuse indexed mapping. |
| A04 | Dependency & shared reuse | Resolve required dependencies and select original source, compatible converted components or registered operation HTTP contracts. This is a logical grouping of dependency resolution and reuse policies. |
| A05 | Conversion orchestrator | Coordinate work, approvals, checkpoints, retries and resume; delegate conversion and delivery. |
| A06 | Native conversion engine | Convert components/configured units and assemble native operation flow; request separate code, metadata, fixture/mock and test generation. |
| A07 | AI execution adapter | Route structured, bounded generation requests through LiteLLM and manage correction attempts. |
| A08 | Build & validation tools | Compile with JDK/Maven, execute JUnit, compare formats and check APIs/settings/source evidence; perform advisory test-strength/review checks. |
| A09 | Standalone & service packaging | Build portable standalone packages and Spring Boot/Helm outputs, including dependencies, runtime configuration and test resources. |
| D01 | Configuration & run profile | Store the saved YAML choices and resolved per-run `state/profile.json`; store credential variable names rather than secret values. |
| D02 | SQLite run database | Store tasks, attempts, approvals, checkpoints, dependency pins, accepted results and evidence in `state/migration.db`. |
| D03 | Analysis cache & AST index | Retain reusable source analysis, indexed Composer relationships and fingerprints. This is analysis data, not converted code. |
| D04 | Shared component registry | Retain converted source, typed APIs, JARs, immutable manifests and versioned artifacts under the configured shared component store. |
| D05 | Shared operation registry | Retain callable operation HTTP contracts, paths and internal/external address metadata. A registry record is not proof of deployment. |
| E01 | Composer workspace | Original source projects, XML definitions, Java classes and classpath inputs. |
| E02 | Migration operator | Choose operations/settings, initiate or resume conversion, and provide required approvals. |
| E03 | AI model / Gemini Studio | External model API used by the configured LiteLLM adapter. |
| E04 | Runnable deliverables | Generated standalone and microservice outputs, shared dependencies, launchers, sample XML, Helm charts and reports. |
| E05 | OpenShift / deployed operations | User-managed target runtime and previously deployed operation APIs. |

## Meaning of the connections

- **Cyan:** module requests and returned results. Two arrowheads indicate an
  exchange, not two independent implementations or a mandatory sequence.
- **Purple, dashed:** persistent reads/writes or lookup/reuse relationships.
- **Gray:** interaction with external source, AI, or deliverable systems.
- **Amber, dashed:** manual image publication and deployment by the user.

The orchestrator is emphasized because it coordinates the participating modules.
The dependency/reuse component consults analysis and both shared registries. The
native engine uses the AI adapter and validation tools. Packaging uses accepted
native code and the same validation toolchain, then produces runnable artifacts.

SQLite is used throughout the converter. The diagram shows its representative
connection to orchestration rather than drawing a separate database line from
every module. Likewise, not every retry, callback, model response, filesystem
write, or runtime HTTP request is drawn.

## Current default policy and boundaries

- Formal fact collection, checklist mapping and fact validation are disabled.
  Source/AST analysis, dependency discovery and source/API/settings checks remain
  enabled.
- AI-generated tests, fixtures and mocks support validation. Actual compilation
  and executed tests remain required; AI approval does not replace them.
- Reused components must match the relevant source/policy/artifact revisions and
  are validated in the current conversion context.
- Called operations use registered HTTP contracts. They are assumed deployed;
  the converter does not deploy a dependency operation automatically.
- Standalone callers use external service addresses. Generated microservices
  use internal OpenShift Service addresses, such as
  `http://service.namespace.svc.cluster.local:8080`.
- Configuration creation, conversion, artifact packaging and deployment are
  separate responsibilities. The diagram does not claim that writing Helm files
  performs a deployment.

## Implementation anchors

The view is grounded in these existing code areas:

- Configuration/startup: `source/cli/`, `source/runtime/configuration.py`,
  `source/runtime/pipeline_runner.py`.
- Mapping/intake/dependencies: `source/runtime/indexed_intake.py`,
  `source/tools/composer_mapper_tools/`, `source/tools/conversion_tools/`,
  `source/tools/java_analysis_tools/source_dependencies/`.
- Orchestration/conversion: `source/runtime/scoped_native/`,
  `source/runtime/component_conversion/`, `source/runtime/behavior_conversion/`.
- AI/testing/builds: `source/runtime/model_execution/`,
  `source/runtime/test_assets/`, `source/runtime/format_comparison/`,
  `source/runtime/managed_projects.py`.
- Persistence/reuse: `source/tools/state_store_tools/`,
  `source/tools/shared_artifact_store/`,
  `source/tools/converted_service_registry_tools/`,
  `source/runtime/operation_reuse/`.
- Packaging/runtime addresses: `source/runtime/service_generation/`,
  `source/runtime/finalization/`, `source/runtime/service_addresses.py`,
  `source/runtime/behavior_conversion/standalone_packaging.py`.
