# Native format library tool

This independent CLI discovers Composer formats/decorators, plans conversion order, prepares
reviewable folders and asks the organization's AI to generate native Java candidates.
It imports no migration-converter runtime, reads no migration database, and does not alter runs.

## Setup

Python 3.11+, JDK 17+ and Maven are needed. Use the Java version configured in config.yaml.
Maven builds only the metadata scanner infrastructure. Generated Java is never compiled or run.
From this directory, create a Python environment and install requirements.txt:

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt

Edit config.yaml. Its source, Java, Eclipse/JAR, Maven and model fields use the corresponding
converter field names and structures. Copy those fields, not the entire converter configuration.
The shipped paths and endpoint are deliberately dummy values. Paths are relative to the YAML.
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

Discovery builds scanner/target/format-library-scanner-1.0.0-jar-with-dependencies.jar if absent.
After changing scanner Java code use discover --rebuild-scanner. No live AI call happens during
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
