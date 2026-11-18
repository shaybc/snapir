# Independent Java policy validator

This directory is a standalone tool. It imports no converter or format-library code and
reads only the common converter YAML for Java/Maven settings. Copy it independently if desired and supply that YAML.

Requires the full JDK (including javac) selected by common java_version/java_home and Python 3 with PyYAML
(installed if missing). Maven is required for the initial build or after validator changes. The launcher
builds only this tool, never the inspected project. Maven build output goes to stderr.

```powershell
python run.py --code "C:\generated\candidate" --policy policy.json
```

Compilation is mandatory on every invocation. There is no enable/disable switch.
The target release defaults to effective java_version. A local target_java_version in config.yaml overrides
it; --release overrides both. java_version/java_home select the full JDK, which may compile for an earlier
release. The policy.json file remains dedicated to dependency and runtime rules.
Repeat `--support PATH` to supply native Java support source directories.
These inputs are validated against the same Java policy and compiled with the candidate.
For example:

```text
python run.py --common-config ../configs/organization.yaml --code candidate --support native-api/src/main/java
```

`run.cmd` accepts the same arguments. After building, Java alone can run it:

```text
java -jar target/java-policy-validator-1.0.0-jar-with-dependencies.jar CODE_PATH POLICY_JSON [COMPILATION_INPUTS_JSON]
```

The optional third Java argument is a JSON file containing `release` and `source_roots`.
It supplies inputs, never enables compilation; omitting it still compiles the candidate.
This low-level Java protocol accepts resolved inputs; use the Python/CMD launcher to read common YAML.

The default common YAML is ../configs/default_config.yaml. Select another with --common-config PATH,
SNAPIR_COMMON_CONFIG or local common_config_path (in that order). Legacy root/sole-profile discovery is
retained when the default file is absent. --config selects this tool's local YAML instead of config.yaml.
Common java_home, java_version, maven_settings_path and maven_local_repository apply to this tool's
infrastructure and default compile target. Explicit local entries override common values, including null.
Paths resolve against their supplying YAML. Explicit --java-home, --java-version, --maven-settings-path,
--maven-local-repository and --release arguments override YAML; the format library uses these to forward
explicit local Java/Maven overrides and the requested compile target. Otherwise this tool's local settings
remain effective. An empty CLI path value clears the common path (matching local null).
No converter code is imported. Native dependency approvals and compile_classpath
remain in policy.json; original classpath_jars/framework_jars are never used as native compile dependencies.

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

For required native third-party libraries, `compile_classpath` in this validator's policy
lists objects containing `coordinate`, `path`, and `sha256`. The coordinate must also be in
`allowed_dependencies`; paths are relative to this policy file. JARs must exist, match their
approved hashes, contain no prohibited framework classes and have no implicit manifest
Class-Path. No IBM/Composer JAR is allowed. Missing libraries produce validation errors
or structured compiler diagnostics. There is no automatic Maven/network resolution.

Compilation uses the JDK compiler API with an explicit isolated classpath, `--release`,
`-proc:none`, an empty processor/source lookup path, and a temporary output directory.
Neither generated code, annotation processors, Maven plugins nor tests are executed.
Compiler errors include file, line, column, diagnostic code and suggested corrections.
The report includes a mandatory `compilation` result, target release and fingerprints of
support sources and approved JARs. Temporary class files are removed after validation.

## Limits and testing

This validates syntax, declared-source policy and compilation. It does not execute tests,
prove behavior or resolve Maven transitives. AST dependency checks remain syntactic; javac
resolves Java types using only the explicit compilation inputs. Reflection checks are conservative and may require replacing ambiguous dynamic
calls with explicit typed native calls. Custom registrations in unrecognized resource
formats are outside the checked registrations. A passing report requires compilation to pass; it is not behavioral verification.

Build with `mvn -f pom.xml package`, then run `python -m pytest tests -q` (pytest is only
needed for this tool's development tests). Tests use synthetic source, never production execution.
