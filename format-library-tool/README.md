# Native format library tool

This independent CLI discovers Composer formats/decorators, plans conversion order, prepares
reviewable folders and asks the organization's AI to generate native Java candidates.
It imports no migration-converter runtime, reads no migration database, and does not alter runs.

## Setup

Python 3.11+, a full JDK and Maven are needed. Use java_home/java_version from the common converter YAML.
Maven builds only tool infrastructure. The independent validator compiles generated Java without running it.
run.cmd validates the selected Python environment's requirements and their active transitive
dependencies locally. If they are already satisfied, no installer or package index is contacted.
Otherwise it runs pip install -r requirements.txt without --upgrade, then validates again.
It installs into the selected interpreter, so an optional dedicated environment is recommended:

    python -m venv .venv

The launcher then validates the configured JDK and builds the scanner and its Maven dependencies
only when the JAR is missing/invalid or its source/build files have changed. A failed installation
or build stops startup. Composer projects and generated components are never built.

Model, source workspace, Java, Eclipse/JAR and Maven defaults are read from ../configs/default_config.yaml.
That file lists all 89 converter settings and their nested defaults. Edit shared organization values there.
Select it with --common-config PATH, SNAPIR_COMMON_CONFIG, or common_config_path in this tool's config.yaml
(in that order) to use another common file. Without a selection, configs/default_config.yaml is used.
Legacy root config.yaml/sole-profile discovery remains available when the default common file is absent.
A missing explicitly selected file is an error. Effective values are built-in fallbacks, then common YAML,
then explicitly supplied local YAML entries. Missing local entries inherit the common value; null and empty
collections override it. Relative paths resolve against the YAML that supplied them. Usually no local overrides are needed.
source_encoding remains an input-specific setting here and is forwarded with the prepared source evidence.
Never put the API key in YAML; set the named environment variable before launching the tool.
FORMAT_LIBRARY_PYTHON optionally selects a different Python executable for run.cmd.

## Workflow

Double-click run.cmd for a menu, or use these commands from this directory:

    run.cmd discover
    run.cmd prepare --select CCString --select NilDecorator --select CCXML
    run.cmd status
    run.cmd convert --folder "C:\path\to\work\components\CCString--groupid"
    run.cmd approve --folder "C:\path\to\work\components\CCString--groupid" --reviewed

A different configuration is selected before the command:

    run.cmd --config "C:\organization\format-library.yaml" discover

Select the converter profile once for this menu session and all child tools:

    run.cmd --common-config "C:\snapir\configs\organization.yaml"

The generated convert.cmd keeps that selection, including when prepare reuses a folder. A changed source
configuration requires discovery again; changed source settings or Java target require fresh preparation.
Endpoint-only changes do not invalidate prepared source evidence. java_version supplies both the JDK
major version and the default target_java_version. An explicit local target_java_version overrides that
compile target; java_version/java_home still select the JDK. Explicit local Java/Maven overrides are forwarded
to the validator. Otherwise its own local settings can override common defaults. The requested compile target is always forwarded.

Shared entries formerly copied here: source_root, java_home, java_version,
java_scan_inactivity_timeout_seconds, classpath_jars, framework_jars, eclipse_classpath_variables,
eclipse_classpath_containers, eclipse_project_classpath_containers, maven_settings_path,
maven_local_repository, model_provider, model_name, model_base_url, model_api_key_environment,
model_timeout_seconds and max_model_attempts. target_java_version defaults to effective java_version.
Any explicit local value for these shared settings takes precedence over the common default.
Output folders, native package, input encoding/excludes, model_stream, source classification rules,
known_dependencies and validator/comparator commands, policies and task limits remain local.

Startup and discovery share the same scanner freshness check for
scanner/target/format-library-scanner-1.0.0-jar-with-dependencies.jar. Source changes rebuild it
automatically; discover --rebuild-scanner explicitly forces a build. No live AI call happens during
discovery, planning, preparation, status, or approval.

Discovery identifies formats by configured FormatElement ancestry through source and JARs.
Decorator ancestry takes precedence. Abstract bases/helpers are supporting evidence, not separate
targets. Dependency cycles are coordinated conversion groups. Preparation automatically includes
the prerequisites of selected components. The printed order is dependency-first.

Source roots and libraries come from Eclipse .classpath project references, library/variable/
configured-container entries, and explicit classpath_jars/framework_jars. JDK classes are inspected
through the platform type solver, never the converter's classloader. For Maven-only dependency
projects supply their effective, ordered dependency JARs through classpath_jars (for example from
the organization's existing dependency export). This tool does not run original Maven projects,
guess transitive versions, resolve arbitrary Eclipse containers, or download application dependencies.
Unresolved evidence is printed and blocks affected prepared groups. Unknown ancestry is explicitly
reported as classification unresolved; it is not silently classified by class or method name.

## Prepared component folders

Folders retain readable class names plus a stable suffix to disambiguate packages.
Cycles use a combined name. Each includes:

    component.json     Original identities, revisions, prerequisites and assigned native classes
    prompt.txt         Full instructions and attachment list, usable manually with internal AI
    sources/           Copied complete original source dependency closure
    jars/              Copied project dependency JARs, never automatic prompt/source attachments
    common-api/        Exact version of NativeFormat, XmlElement and FormatContext
    prerequisites/     Immutable copies of approved native dependencies, refreshed at conversion
    convert.cmd        Double-click entry point into this tool with the selected configuration
    generated/         A separate candidate directory for each successful attempt
    attempts/          Requests, delivered/partial responses, and outcome diagnostics

Existing folders are never overwritten with different evidence/settings. Use a new output_root
after changing source revisions, native package, API or pinned dependencies, then discover/prepare
again. Repeating prepare for identical evidence keeps human edits and generated candidates.
Do not edit original sources, JARs, component.json or common-api copies inside prepared folders.
The tool verifies their hashes before model calls. Human edits belong in the candidate directory.

## Settings and composition

The generated implementation owns parsing the operation definition attributes, original defaults,
initializeFrom behavior, validation and the resulting native flags/settings.
The prompt requires a public constructor accepting Map<String,String> attributes. Decorators also
receive their wrapped NativeFormat. Wrappers receive native children and occurrence bindings.
The AI records the real native constructor declarations, not an attribute-to-flag metadata catalog.
The tool does not implement parsing rules, decorator ordering, conditional execution, before/after
hooks or wrapper assembly itself.

The common API is version 1. Both directions use XmlElement and shared FormatContext fields.
Generated code must preserve source behavior and must not recreate a Composer runtime.
Approved dependencies are supplied with actual native code/declarations. Supporting original
sources do not become extra exported targets. Missing executable behavior must be reported by
the AI as blocked; a JAR filename is not proof that the AI has its method bodies.
Only source text, the common API, and approved prerequisite production sources/descriptors are
sent. Requests exceeding request_character_limit are refused without truncation.

## API delivery and output

Supported providers are litellm and gemini. LiteLLM can address an organization's compatible
OpenAI-style bridge using its model name and endpoint. Standard complete responses are the default.
Set model_stream: true only when the endpoint supports streaming. No provider API-key value is
saved in prepared artifacts.

Each attempt runs in an isolated worker process. model_timeout_seconds measures inactivity since
real nonempty response content, not overall duration. Heartbeats/empty stream chunks do not extend
it. With complete responses there is no observable model progress until the message arrives.
An inactive worker is terminated before a delivery retry starts. HTML, empty, upstream error
and interrupted responses are delivery failures, not JSON-correction prompts. Partial content
is retained locally. The tool does not automatically send an invalid JSON response for correction.

The response must be one JSON object with status generated, complete files, exported components,
actual constructor declarations, dependencies and notes; prompt.txt gives the exact shape.
Alternatively status blocked must explain missing evidence. Extraction checks structure, target
identities, production-file paths, package paths and pinned dependency declarations. These are
structural checks only: they do not prove that Java compiles or matches Composer behavior.
Failed attempts preserve previous candidates. Successful output is saved under
generated/<attempt-id>/, with latest.json pointing to the newest candidate.

## Review and shared publication

Inspect/edit the latest candidate and its candidate.json constructor declarations if necessary.
Approval requires the explicit --reviewed flag or confirmation in the menu. It records actual
reviewed bytes, preserves older approvals, and sets verified=false: human approval is not a test pass.
Publish only after your organization's review process.

approved_library_root contains immutable <group-id>/<revision>/ artifacts, an index.json pointing
to current approved revisions, and common-api/<api-hash>/ shared Java sources. Constructor
declarations identify the actual native API; they do not interpret individual XML settings.

Later conversions require approvals matching the original source and common API revisions.
Changed prerequisite approvals invalidate dependent publication until regeneration. File tampering
is rejected. Concurrent conversion/publication is refused using tool-owned lock files. After a
process crash, verify it is stopped before manually removing its stale lock.

There is no migration-converter integration yet. This tool produces a reviewed source library,
not a Maven release, automatic registration, unit tests, comparison tests, or executable test runs.
Tool regression tests use synthetic sources and fake model deliveries only.

## Standalone discovery and dependency diagnostics

`source_encoding` selects the encoding of original and decompiled `.java` files, defaulting
to `UTF-8`. For example, set `source_encoding: windows-1255` for Hebrew Windows sources.
This setting applies to direct parsing, dependency source resolution and original-source
AI attachments. YAML, logs, generated code and common API files remain UTF-8. No encoding
is guessed and original files are not rewritten. For mixed encodings, normalize the sources
to one encoding first. Unreadable files are skipped with their path, encoding and error in
`logs/discovery.log`; remaining files are still scanned. Missing required source dependencies
can still block affected components. Rediscover and prepare fresh folders after changing
the encoding; prepared folders retain the encoding used for their original evidence.

Discovery checks inheritance first. Unrelated classes are not inspected for method/field
failures; unresolved ancestry is recorded in `work/logs/discovery.log`. The console lists
identified formats/decorators, deduplicated missing dependencies and the log location.

Each formatter has its own required-member scope: format/unformat, initialization,
constructors, reached source calls, inherited overrides and field initializers. Unused
helper methods do not contribute blockers. Qualified names such as `java.util.Calendar`
are treated as types. Abstract runtime delegation is recorded without guessing its target.
Whole original source files remain intact as evidence; `component.json` and `prompt.txt`
identify required members. Shared ancestors are evidence for the standalone conversion,
not separately approved foundation targets. No foundation configuration is required.

Eclipse test entries, JUnit containers and test source roots are excluded. Maven test-scope
dependencies do not require a production classpath. Missing classpath declarations remain
diagnostics; missing symbols in required members block the affected formatter. Declared
production JARs remain available as dependencies rather than uploaded source bodies.

Prepared sources use their Java package paths, adding a readable project folder only for
collisions. Hashes remain in `component.json`. Existing folders are immutable: rediscover
and use a new output_root to replace older dependency evidence and prepared layouts.

## External candidate policy validation

Generation stages returned production files under `attempts/<id>/candidate/`, then invokes
an independent CLI. No validator code is imported. The default command uses the current
Python interpreter and `../java-policy-validator/run.py`; override `validator_command` with
a YAML list of executable/arguments. `validator_policy_path` identifies the validator's own
JSON policy, and `validator_timeout_seconds` bounds the complete invocation (including its
first build). The command receives `--code PATH --policy PATH --release TARGET` and native
`--support PATH` inputs and must return the documented
JSON report and exit codes. See `../java-policy-validator/README.md` for policy configuration.

Only a complete passing report matching all staged file bytes and policy bytes allows a
candidate to be published under `generated`. Successful compilation for the configured target
Java version is mandatory. Native common API sources and approved prerequisite Java sources
are supplied automatically; no compile-enabling flag or configuration is needed. Support-source
fingerprints must match, and older reports without a passing compilation result are rejected.
Approved third-party JARs belong in the independent validator policy's `compile_classpath`,
not the Composer classpath. Compilation diagnostics are in `validation.json` and can be sent
to the AI for correction. No generated code, annotation processors or tests are run.
JSON response metadata is not inspected as
Java. Reports and captured output are saved in the attempt as `validation.json`,
`validator.stdout.txt` and `validator.stderr.txt`; rejection details are in
`validation-rejection.json`. Rejected candidates remain staged for inspection and AI feedback.
The previous accepted candidate is preserved. Delivery retries remain unchanged; policy
findings do not yet initiate an automatic AI repair. Approval continues to allow human edits
and records their actual bytes; the generation report describes pre-review bytes only.

## Independent staged behavior comparison

After generation passes policy/compilation validation, the format-library tool invokes the
separate `java-behavior-comparator` CLI. Both tools read the same selected converter YAML for the
organization AI provider, endpoint and key environment variable. The comparator's own config.yaml
contains comparison-specific limits only. No comparator module is imported into this application.

`comparison_command` selects the executable/argument list (default current Python plus the
sibling comparator run.py). `comparison_config_path` points to its independent YAML and
`comparison_timeout_seconds` bounds the subprocess. Original copied sources/JARs, source
encoding, the original/native target class pairs, staged generated source and native API/
approved prerequisite sources are supplied through `comparison-request.json`. The entry
scope is original format/unformat/initialization/before hooks and generated format/unformat,
plus constructors, fields and reached helpers. This does not compare all framework utility APIs.

Only a complete `consistent_in_review` decision matching the inspected bytes allows publication.
This is a static AI review, not behavioral verification: candidates still have verified=false.
Differences, inconclusive work, missing comparator configuration, stale evidence or tool failure
retain the staged candidate and preserve the previous accepted candidate. Existing human approval
and delivery-only retry behavior remain unchanged; repair remarks are not automatically applied.

Read attempts/<id>/comparison.json and comparison-feedback.json for the decision and suggested
corrections with source locations. comparator.stdout.txt and comparator.stderr.txt retain transport
output. comparison-work/ contains resumable stage evidence and a short Markdown report. To resume
an interrupted review directly, run the comparator with this attempt's request/output paths.
All generation entry paths use the same extraction handoff. Discovery/preparation do not call AI
comparison. Approval of human edits still records reviewed bytes and does not claim the generation
review applies to subsequent edits. The converter and independent policy validator are unchanged.
