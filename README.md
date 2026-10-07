# snapir

## Java toolchain

Generated components, shared libraries, operation services, and composer-mapper target Java 25. Use JDK 25 for `java`, `javac`, and Maven (check `mvn -version`; Maven uses `JAVA_HOME`). Generated managed POMs enforce JDK 25 and `maven.compiler.release=25`; incompatible existing POMs must be regenerated in a new run. Spring Boot is pinned to 3.5.16, whose [official requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html) include Java 25 compatibility.

Deployment manifests reference a supplied `image_name`; they do not build or inspect that image. Supply an image running JRE/JDK 25 and verify `java -version` inside it before deployment. Legacy source build metadata and third-party dependency bytecode targets remain unchanged.


## Migration run folder contents

Each migration run has its own folder under `work/migration_runs/<run-id>` (or the configured `output_root`). The table below describes the artifacts produced by a successful deterministic intake and legacy analysis stage.

After intake, the run pauses at `planning_inputs_ready`, before model-driven migration planning. These artifacts describe the legacy workspace and prepare planning inputs; generated services are added in later stages. Failed or earlier paused runs may contain only some of these artifacts.

| File or folder | Contents |
| --- | --- |
| `vault/` | Mapper-produced Markdown describing the legacy workspace: operations, operation steps (`opsteps/`), Java classes, contexts, formats, channels, and analysis. |
| `generated/` | Migrated application output area; generated services are added in later stages. |
| `reports/run_config.json` | Effective run settings snapshot, also persisted in the database. |
| `state/profile.json` | Validated project configuration snapshot with resolved paths. |
| `reports/java_source_index.json` | Discovered Java source files and any source discovery issues. |
| `reports/java_classpath_index.json` | Discovered Java classpath information, including compiled types, libraries, and discovery issues. |
| `reports/component_inventory.json` | Legacy components and their relationships. |
| `reports/java_source_dependencies.json` | Dependencies between Java source components. |
| `reports/component_usage.json` | Implementation component usage. |
| `reports/configured_component_usage.json` | Component usage identified through legacy configuration. |
| `reports/planning_inputs.json` | Operation summaries ready for migration planning. |
| `state/migration.db` | SQLite database containing run state and structured analysis. |
| `logs/mapper.log` | Captured mapper standard output and standard error. |

Continuation requires `state/` and the mapper inputs in `vault/`; intake inspection reports are optional for continuation. Original sources remain external to the run folder. Later-stage gate reports, closures, and review evidence retain their existing locations. New runs use this layout only; existing runs are not migrated.

## Run status and current phase

Run state uses two fields with different meanings:

| Field | Meaning | Examples |
| --- | --- | --- |
| `status` | Overall run condition. | `paused`, `in_progress`, `failed`, `blocked`, `completed` |
| `current_phase` | Current checkpoint or activity. | `planning_inputs_ready`, `planning_failed` |

For example, `status=paused` with `current_phase=planning_inputs_ready` means intake completed successfully and the run is ready for migration planning. `status=failed` with `current_phase=planning_failed` means planning was attempted and errored; this checkpoint alone does not identify the cause, and does not imply a credentials problem.

## Migration workflow groups

The workflow can be understood as seven conceptual groups:

1. **Intake and legacy analysis:** inspect the legacy workspace, run the mapper, and prepare planning inputs.
2. **Migration planning and approval gate 1:** create and validate the migration plan, then obtain plan approval.
3. **Dependency closure and component conversion:** resolve operation dependencies and convert the required components.
4. **Component review and approval gate 2:** review converted components, address findings, and obtain component approval.
5. **Operation assembly/review and approval gate 3:** assemble operation implementations, review them, address findings, and obtain operation approval.
6. **Service generation and validation:** generate service projects, build and validate them, and collect validation evidence.
7. **Final validation and approval gate 4:** check final deliverables and validation evidence, then obtain final migration approval.

These groups are a conceptual overview, not an exact fixed database phase enumeration. Each group can involve waiting, blocking, failure, or correction checkpoints as applicable. The database stores `current_phase` as a string, with more specific checkpoints such as `gate_1_pending`, `closures_blocked`, `component_revision`, and `assembly_correction_pending`.
