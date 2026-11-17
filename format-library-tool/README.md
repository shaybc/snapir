# Native format library tool

This independent CLI discovers Composer formats/decorators, plans conversion order, prepares
reviewable folders and asks the organization's AI to generate native Java candidates.
It imports no migration-converter runtime, reads no migration database, and does not alter runs.

## Setup

Python 3.11+, JDK 17+ and Maven are needed. Use the Java version configured in config.yaml.
Maven builds only the metadata scanner infrastructure. Generated Java is never compiled or run.
run.cmd validates the selected Python environment's requirements and their active transitive
dependencies locally. If they are already satisfied, no installer or package index is contacted.
Otherwise it runs pip install -r requirements.txt without --upgrade, then validates again.
It installs into the selected interpreter, so an optional dedicated environment is recommended:

    python -m venv .venv

The launcher then validates the configured JDK and builds the scanner and its Maven dependencies
only when the JAR is missing/invalid or its source/build files have changed. A failed installation
or build stops startup. Composer projects and generated components are never built.

Edit config.yaml. Its source, Java, Eclipse/JAR, Maven and model fields use the corresponding
converter field names and structures. Copy those fields, not the entire converter configuration.
The shipped paths and endpoint are deliberately dummy values. Paths are relative to the YAML.
Never put the API key in YAML; set the named environment variable before launching the tool.
FORMAT_LIBRARY_PYTHON optionally selects a different Python executable for run.cmd.

## Workflow

Double-click run.cmd for a menu, or use these commands from this directory:

    run.cmd discover
    run.cmd prepare --stage foundation
    run.cmd prepare --stage component --select CCString --select NilDecorator --select CCXML
    run.cmd status
    run.cmd convert --folder "C:\path\to\work\components\CCString--groupid"
    run.cmd approve --folder "C:\path\to\work\components\CCString--groupid" --reviewed

A different configuration is selected before the command:

    run.cmd --config "C:\organization\format-library.yaml" discover

Startup and discovery share the same scanner freshness check for
scanner/target/format-library-scanner-1.0.0-jar-with-dependencies.jar. Source changes rebuild it
automatically; discover --rebuild-scanner explicitly forces a build. No live AI call happens during
discovery, planning, preparation, status, or approval.

Discovery identifies formats by configured FormatElement ancestry through source and JARs.
Decorator ancestry takes precedence. Concrete formats/decorators are component targets. Abstract
bases and helpers can be explicitly selected as foundation targets; framework JAR membership alone
does not authorize converting an entire archive. Dependency cycles are coordinated conversion
groups. Preparation automatically includes selected components' prerequisites.

## Foundations first

Run discover to review its FOUNDATION BASE proposals, consumer classes and source availability.
Then configure the exact original shared classes to convert together. For example:

    foundation_source_roots:
      - C:/organization/framework-sources
    foundation_groups:
      field_base:
        - com.ibm.dse.base.FormatElement
        - com.ibm.dse.base.FieldFormat

These are examples, not an assumed complete inheritance chain for your application. Include other
shared ancestors/helpers where their actual behavior requires it. Exact source is required for
selected classes, including those otherwise supplied only by a JAR. The tool does not decompile
archives or invent missing method bodies. Duplicate source definitions and unresolved dependencies
remain blockers. JDK classes are not foundation conversion targets.

After changing these settings, run discover again. Then use prepare --stage foundation (optionally
--select field_base) to prepare the shared tasks. Convert each foundation folder using its
convert.cmd, review its generated candidate, and approve it using the existing approve --reviewed
command. Preparation does not perform AI calls and does not automatically approve anything.

Foundation prompts allow an abstract native base, utility classes and native interfaces. Several
original ancestors may become one base, or cooperating exports may split their responsibilities.
The AI declares covered_original_classes, native_class, kind, actual constructors/public methods,
protected hooks, and integration_notes for each export. Every selected original must be covered.
This is an extension contract for later code generation, not XML attribute-to-flag metadata.
Foundation utility exports do not have to implement NativeFormat or expose both directions.
Original Tag loading, reflection-based factories and general Composer runtime reconstruction
remain excluded. The common NativeFormat/XmlElement/FormatContext API stays at version 1.

Prepare the individual components with prepare --stage component --select CCString. Its required
foundation folders are included automatically. Conversion is blocked until matching foundations
are approved. The AI receives the component-specific original behavior plus the approved native
bases, constructors and protected hooks. It inherits or delegates through those frozen contracts
and implements only its remaining differences. It may not regenerate approved prerequisite files.

Prepared folders keep the complete original source closure for human review. At conversion time,
files wholly covered by approved exports are omitted from AI attachments. Mixed files containing
both covered and needed uncovered declarations remain attached and are marked evidence-only for
the approved portions. prompt.txt and request.json record what was omitted and why. Only the
actual prerequisite artifacts are supplied, never the entire approved library. Size limits remain
in force; no evidence is silently truncated.

Valid plans place foundation groups before components. A foundation dependency on a concrete
component or a cross-stage cycle is blocked for explicit boundary review, not silently folded
into an executable framework. Status identifies stages, missing approvals, and stale candidates.

Plans, preparations, candidates and approvals use the approved-foundations-v2 policy. Older folders
and approvals remain on disk but cannot silently satisfy this workflow. Use a new output_root,
rediscover, and explicitly generate/review/approve the relevant tasks again. Source, ownership,
native files, common API or prerequisite changes invalidate reuse/publication where applicable.
Changing foundation settings also requires a fresh discovery/preparation. Approval still records
verified=false: no generated component is compiled, tested, or executed by this tool.

Source roots and libraries come from Eclipse .classpath project references, library/variable/
configured-container entries, and explicit classpath_jars/framework_jars. JDK classes are inspected
through the platform type solver, never the converter's classloader. For Maven-only dependency
projects supply their effective, ordered dependency JARs through classpath_jars (for example from
the organization's existing dependency export). This tool does not run original Maven projects,
guess transitive versions, resolve arbitrary Eclipse containers, or download application dependencies.
Discovery checks inheritance first. Classes proven unrelated are ignored unless they are required
supporting code for a format/decorator or explicitly selected foundation. Their field and method
dependencies are not inspected. Unresolved ancestry is retained as a warning in the detailed log,
not silently classified by class or method name.

The console summary lists identified concrete formats/decorators, one deduplicated list of missing
or unresolved classes/dependencies, and the detailed log location. Full per-class warnings,
dependency owners, foundation proposals, conversion order and blockers are written to
output_root/logs/discovery.log. Structured facts remain in discovery.json and plan.json.
Missing evidence still blocks affected prepared groups; unrelated method/field failures do not.

Dependency inspection follows format/unformat entry points, initialization, constructors and
source-resolved calls, including inherited overrides and reached field initializers. Each formatter
has its own member scope, so another formatter's use of an unrelated helper method does not add
blockers to it. Copied source files remain intact for review; required_members in component.json
and prompt.txt identifies the relevant members. Abstract runtime delegation remains explicit rather
than guessing every possible implementation. Unresolved calls on a required path still block.

Qualified type scopes such as java.util.Calendar are resolved as types, not reported as fields.
Eclipse entries marked test=true, JUnit containers and test source roots are excluded from production
discovery. Maven test-scope dependencies do not require a production classpath. Compile/provided
dependencies and explicitly configured classpath_jars remain production inputs.
Unresolved classpath declarations remain diagnostic warnings. With member-scoped discovery,
they block preparation only when required source resolution also reports a missing dependency;
missing declared JAR files are recorded in component.json dependency_warnings.

## Prepared component folders

Foundation folders are under work/foundations/; concrete folders are under work/components/.
Folders retain readable class names plus a stable suffix to disambiguate packages.
Cycles use a combined name. Each includes:

    component.json     Original identities, revisions, prerequisites and assigned native classes
    prompt.txt         Full instructions and attachment list, usable manually with internal AI
    sources/           Copied original source closure arranged by Java package
    jars/              Copied project dependency JARs, never automatic prompt/source attachments
    common-api/        Exact version of NativeFormat, XmlElement and FormatContext
    prerequisites/     Immutable copies of approved native dependencies, refreshed at conversion
    convert.cmd        Double-click entry point into this tool with the selected configuration
    generated/         A separate candidate directory for each successful attempt
    attempts/          Requests, delivered/partial responses, and outcome diagnostics

Newly prepared sources use paths such as sources/com/ibm/il/dse/cc/format/CCString.java.
Only a colliding package/filename receives a readable project prefix, for example
sources/project-Orders/com/example/Shared.java. Repeated project names include readable ancestor
names. Original locations and SHA-256 hashes remain in component.json; JAR layout is unchanged.
Previously prepared folders keep their existing paths. Use a new output_root and prepare again
to obtain the new layout without changing old candidates or approvals.

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
actual constructor declarations, dependencies and notes; each stage's prompt.txt gives its exact
shape. Foundation exports additionally declare original coverage, methods, hooks and extension notes.
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
