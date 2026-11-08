# Snapir system context and workflow

This is the Level 1 overview of the current default conversion path. It combines
the main workflow with its stores and external systems. The diagram follows the
repository implementation; it is not an IcePanel export.

- [PNG image](snapir-system-context.png)
- [SVG image](snapir-system-context.svg)
- [Editable draw.io master](snapir-system-context.drawio)

The PNG and SVG are static images. The draw.io master preserves stable component
IDs and editable boxes/connectors. Future drill-downs can use the same IDs, such
as **C04 dependency closure**, **C07 native conversion**, or **S02 shared reuse**.
Lower-level drill-down pages have not been created yet.

## Reading the workflow

1. **C01–C02:** the operator saves configuration YAML, then starts a run. Startup
   resolves paths/settings, saves the effective profile, and opens the run database.
   Saving configuration alone does not start conversion.
2. **C03–C05:** the converter generates or validates an indexed Composer map,
   expands the selected operations' dependencies, and creates the execution plan.
   Approval policies can pause the workflow at its gates.
3. **C06–C08:** it consults shared registries, generates missing native Java in
   dependency order, then compiles and executes tests. Existing shared candidates
   still undergo current-scope validation. Called operations use registered HTTP
   contracts; the converter does not silently embed their standalone artifacts.
4. **C09–C10:** it packages the runnable standalone operation and generates the
   microservice wrapper, executable JAR, and Helm chart. Shared dependencies and
   test/demo assets are included where required.
5. **S05:** the user publishes images and deploys services. Existing called
   operations are assumed deployed; conversion does not deploy them automatically.

## Component index and source anchors

Paths below are relative to the repository root. Each row identifies the code
areas to inspect when creating the corresponding drill-down.

| ID | Component | Main responsibility and source anchors |
| --- | --- | --- |
| U01 | Migration operator | Select source and scope, start/resume, review approval gates. `source/cli/main.py` |
| E01 | Composer workspace | Original Java/XML definitions and classpath inputs across projects. Read as source evidence. `source/tools/source_discovery_tools/` |
| S00 | Reusable analysis / AST index | Verified indexed Composer maps, source fingerprints, and reusable workspace analysis. `source/tools/composer_mapper_tools/indexed_analysis.py`; `source/tools/state_store_tools/workspace_analysis.py` |
| C01 | Configuration wizard | Create Default Config fixes the supported full flow; Advanced Configuration retains the existing configurable wizard. `source/cli/default_configuration_flow.py`; `source/cli/default_configuration_settings.py`; `source/cli/configuration_wizard.py` |
| C02 | Run startup & profile | Resolve configuration, create run folders, save `state/profile.json`, initialize `state/migration.db`. `source/runtime/configuration.py`; `source/runtime/pipeline_runner.py`; `source/runtime/workspace_paths.py` |
| C03 | Composer Mapper & AST | Generate or reuse indexed/scoped analysis; verify workspace identity and current source fingerprints. `source/runtime/indexed_intake.py`; `source/tools/composer_mapper_tools/` |
| C04 | Automatic dependency closure | Expand requested roots and locate their required classes, formats, operation steps and operations across projects. `source/tools/conversion_tools/scoped_workflow/`; `source/tools/java_analysis_tools/source_dependencies/`; `source/tools/conversion_tools/component_graph.py` |
| C05 | Plan, gates & orchestration | Persist scoped tasks/batches, honor configured approvals, track checkpoints, and route retries/resume. `source/runtime/scoped_native/runner.py`; `source/runtime/human_gates.py`; `source/runtime/checkpoints.py` |
| C06 | Shared reuse resolver | Match shared component candidates, restore pinned artifacts, and resolve registered operation APIs. `source/runtime/component_conversion/shared_reuse.py`; `source/runtime/operation_reuse/`; `source/runtime/service_addresses.py` |
| C07 | Native Java conversion | Generate components before configured units and operation assembly; separate code, metadata, fixtures/scenarios and tests. `source/runtime/component_conversion/runner.py`; `source/runtime/behavior_conversion/staged_pipeline.py`; `source/runtime/behavior_conversion/runner.py`; `source/runtime/test_assets/` |
| C08 | Build & validation | Require actual compilation and executed JUnit; check typed APIs/settings/source freshness; compare formats using tests/mocks. `source/runtime/behavior_conversion/verification_ladder.py`; `source/runtime/behavior_conversion/conversion_readiness.py`; `source/runtime/format_comparison/` |
| C09 | Standalone & portable output | Runnable operation, launchers, validated XML example, shared dependencies, runtime configuration and test/demo resources. `source/runtime/operation_reuse/runtime_settings.py`; `source/runtime/component_conversion/shared_dependencies.py`; `source/runtime/behavior_conversion/standalone_packaging.py`; `source/runtime/behavior_conversion/standalone_runner.py` |
| C10 | Microservice & Helm output | Generate and validate HTTP wrapper, executable JAR, Helm chart and editable deployment values. `source/runtime/service_generation/`; `source/tools/deployment_tools/`; `source/runtime/finalization/runner.py` |
| S01 | Run state · SQLite | Per-run tasks, approvals, attempts, dependencies, pinned revisions, checkpoints and evidence. `source/tools/state_store_tools/`; `source/runtime/workspace_paths.py` |
| S02 | Persistent shared registries | Shared component source/contracts/JARs and registered operation HTTP contracts/address metadata. `source/tools/shared_artifact_store/`; `source/tools/converted_service_registry_tools/` |
| S03 | Live AI provider | LiteLLM routes requests to the configured model, including Gemini Studio. Keys come from environment variables. `source/runtime/model_execution/` |
| S04 | Deliverables & evidence | Generated projects/packages, logs, reports, manifests and validation receipts. `source/runtime/workspace_paths.py`; `source/runtime/finalization/runner.py` |
| S05 | OpenShift & deployed services | External runtime managed by the user. Generated clients use the appropriate address for standalone or in-cluster execution. `source/runtime/service_addresses.py`; `source/runtime/operation_reuse/runtime_settings.py` |

## Important distinctions

- **Configuration versus profile:** YAML records user inputs and selected policy;
  the per-run profile records resolved effective settings used by that run.
- **Run database versus shared registries:** the database tracks one run. The
  configured persistent shared store supports reuse across runs. Default shared
  registry locations are `shared/components` and `shared/operations`.
- **Mapping versus conversion:** the map describes source structure and
  dependencies. AI/native generation happens later; reusing a map does not turn
  conversion off.
- **Facts disabled versus analysis enabled:** the default path disables formal
  fact collection, checklist mapping and fact validation. AST parsing, source
  fingerprints, dependency analysis, API checks and settings checks remain active.
- **Validation versus proof of equivalence:** compilation and executed tests are
  required. Format comparison uses observed cases. Advisory mutation tests and AI
  review do not establish exhaustive equivalence.
- **Internal versus external URLs:** microservice callers use internal OpenShift
  Service addresses, such as `http://service.namespace.svc.cluster.local:8080`.
  Standalone callers use external URLs or explicit overrides. Operation HTTP
  paths are part of the registered API contract, separate from its base address.
- **Generation versus deployment:** executable code, Helm files and deployment
  settings are generated and validated. The user handles image publication and
  deployment. Existing `values.yaml` edits are preserved.
- **Recovery:** missing indexes can be reconstructed from retained manifests;
  missing compiled artifacts can be rebuilt from retained source when compatible.
  Missing source/artifacts or changed fingerprints require the relevant work to
  run again. Deleting all shared artifacts removes that reuse history.

The overview deliberately shows only principal exchanges. All stages persist
progress and evidence in S01; not every database write, model response, retry,
gate or runtime HTTP call has a separate arrow.
