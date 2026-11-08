# Open issues

## 1. Identify dependency JARs and exact versions, and supply relevant conversion context

Intake currently identifies class availability and the JAR or Java runtime that
provides each class. It does not reliably establish Maven coordinates and exact
versions for every external JAR.

- Discover all dependency JARs from Maven, Eclipse classpaths, configured libraries,
  and resolved project dependencies.
- Determine exact artifact versions and Maven coordinates where available, recording
  their provenance. Investigate resolved Maven metadata, embedded `pom.properties`,
  and JAR manifests; report unresolved or conflicting identities explicitly.
- Map source classes to the external classes and artifacts they actually depend on.
- Design how to supply each relevant source conversion request with its dependency
  identities, exact versions, and useful API/documentation context, avoiding unrelated
  libraries and repeated context.
- Verify generated code against those identified dependencies through compilation
  and appropriate tests.

## 2. Log the source file before processing it

Implemented locally and covered by mapper regression tests.

Before processing each source file or rendering each mapper inventory definition,
write a message to both the console and the corresponding log file. Include the
source file's full path and the current processing phase. For inventory definitions,
also include the definition name and XML selector when available.

- Write the message before starting the work, not only after completion or at
  sampled progress intervals.
- Ensure the message is flushed so it remains available if processing crashes.
- After a crash, the last start message should identify the file and definition
  being processed immediately before the failure.

Indexed mapping also saves a completed source-index checkpoint before rendering.
Recovery through `--resume-analysis` validates that checkpoint and restarts rendering
in a fresh destination; stale or damaged checkpoints require rebuilding the index.
See [mapper recovery instructions](docs/composer_analysis_store.md).
