# Independent Java policy validator

This directory is a standalone tool. It imports no converter or format-library code and
reads none of their configurations. Copy it independently if desired.

Requires Java 17+ and Python 3 (standard library only). Maven is required for the initial
build or after validator changes. Set JAVA_HOME/PATH for your JDK and Maven. The launcher
builds only this tool, never the inspected project. Maven build output goes to stderr.

```powershell
python run.py --code "C:\generated\candidate" --policy policy.json
```

`run.cmd` accepts the same arguments. After building, Java alone can run it:

```text
java -jar target/java-policy-validator-1.0.0-jar-with-dependencies.jar CODE_PATH POLICY_JSON
```

Stdout is one JSON object. Exit codes are 0 passed, 1 findings, 2 validator failure.
The report includes schema/tool/policy versions, policy SHA-256, per-file SHA-256,
a combined input fingerprint, and findings with rule, file, line (0 when unavailable),
reference, explanation and suggested correction. Syntax and policy failures are distinct
from validator infrastructure failures. Reports are suitable as AI repair feedback.

## Policy

Edit this tool's `policy.json`. It is intentionally independent of caller configuration.
`forbidden_packages` rejects IBM/Composer and legacy server framework references.
`forbidden_reflection_packages` plus AST lookup checks reject reflective and dynamic
class loading APIs. Comments, Javadoc, ordinary literals, and external response metadata
are not Java dependencies. All Java files, including unused helpers, are inspected.

`allowed_dependencies` and `allowed_plugins` contain exact `groupId:artifactId:version`
strings. Default empty lists mean JDK-only generated projects. Add explicitly approved
native third-party coordinates here; callers' model dependency catalogs do not implicitly
approve them. `allowed_repositories` contains exact approved repository URLs. Even listed
IBM coordinates remain prohibited. Versions must be fixed; ranges, SNAPSHOT versions,
external parents, extensions, systemPath JARs and unresolved Maven properties are rejected.
All declared profiles and dependency/plugin-management sections are checked conservatively.
No inspected build/plugin is executed. XML DTDs and external entities are not allowed.
Service provider files and XML class/type registrations are checked for prohibited names.
Opaque JAR/class files and symlinks are not accepted as generated source evidence.

## Limits and testing

This validates syntax and a conservative declared-source policy. It does not compile,
execute tests, prove behavior, resolve Maven transitives or symbol-resolve arbitrary simple
Java names. Reflection checks are conservative and may require replacing ambiguous dynamic
calls with explicit typed native calls. Custom registrations in unrecognized resource
formats are outside the checked registrations. A passing report is not a compilation pass.

Build with `mvn -f pom.xml package`, then run `python -m pytest tests -q` (pytest is only
needed for this tool's development tests). Tests use synthetic source, never production execution.
