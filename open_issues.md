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
