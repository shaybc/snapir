# Independent Java behavior comparator

This standalone read-only tool compares original and generated Java through small AI tasks.
It imports no converter, format-library, or validator code. Its only shared configuration input is the converter YAML.
It writes only comparator-owned reports/cache/build output. It never edits, compiles, executes,
repairs or approves the inspected implementations. Maven builds only its own source indexer.

## Setup

Install Python 3, the JDK selected by common java_home/java_version and Maven on PATH. `run.cmd`
uses Python and installs only missing requirements from this directory. The first index run
builds `indexer/pom.xml`; later runs verify its content hashes and reuse the built JAR.

Keep comparison limits in this tool's config.yaml. Shared defaults come from ../configs/default_config.yaml,
which lists every converter field and its default. Explicit local shared fields override common defaults.
--common-config PATH wins, followed by SNAPIR_COMMON_CONFIG, then local common_config_path. Otherwise use
configs/default_config.yaml; legacy root/sole-profile discovery is retained if that file is absent.
Relative paths resolve against the supplying YAML. Missing local values inherit common defaults; explicit
null/empty settings replace them. A comparator-local connection override is honored even when called by the format library.
The format-library caller passes the selected common path automatically; it does not import comparator code.

Moved entries: model_provider, model_name, model_base_url, model_api_key_environment,
model_timeout_seconds, max_model_attempts and java_home. java_version, maven_settings_path and
maven_local_repository are also consumed from the common YAML for indexer selection/builds.
max_model_calls, max_run_seconds, evidence/task limits, index_timeout_seconds, source_excludes and
maven_command remain local. The original/generated source locations and encodings stay explicit request inputs.
LiteLLM uses its own SDK adapter with the same provider-prefixed model names as the converter. Gemini
uses google-genai (an empty model_base_url uses its standard endpoint). Old openai_compatible/openai
transport remains supported. mock permits indexing but cannot produce behavior approval.
Responses are non-streaming. Set the common model_api_key_environment variable; credentials are not stored in artifacts.

## CLI

```powershell
run.cmd index --original "C:\legacy\StringFormatHolder.java" --original-source "C:\legacy\sources" --generated "C:\native\src" --output "C:\reviews\string"
run.cmd compare --original "C:\legacy\StringFormatHolder.java" --original-source "C:\legacy\sources" --original-jar "C:\legacy\framework.jar" --generated "C:\native\src" --generated-source "C:\native-api\src" --original-class com.example.StringFormatHolder --generated-class com.example.NativeStringFormatHolder --output "C:\reviews\string"
```

Both `python run.py` and `run.cmd` accept those arguments. Repeat source/JAR arguments for
additional dependency locations. Supply folders, not a manually enumerated dependency class
list. If each side has exactly one target class it is selected automatically. Otherwise
use both class selectors; ambiguous selections list available classes instead of guessing.
Use --original-encoding and --generated-encoding for source encodings (default UTF-8).

For live caller progress, optionally supply --progress-file STATUS_JSON or set
JAVA_BEHAVIOR_PROGRESS_PATH to that path. The format-library caller sets it automatically.
The small java-behavior-progress-v1 snapshot contains phase, activity, model_call and the
current model_timeout_seconds. It is replaced atomically, contains no prompts/source/credentials,
and does not affect deadlines, task cache identities or comparison decisions. An unwritable
progress file or one inside inspected inputs is ignored. Stdout remains exactly the canonical final JSON result.

`index` needs no AI key and saves a source catalog. `compare` runs these controlled stages:
1. AST member, inheritance, branch, return, exception, write and call inventory.
2. Proposed API input/output/context/exception mapping with explicit uncertainties.
3. Original behavior identification, one member at a time, with per-fact accounting.
4. Paged counterpart discovery and one-behavior source-based comparison.
5. A separate challenge/review of every claimed behavioral difference.
6. Reverse generated-member accounting and related behavior interaction checks.

All prompts are short stage-specific instructions stored in the corresponding modules.
Members and immediate callee/field context are supplied intact. Tasks can request additional
indexed evidence. Oversized evidence produces an incomplete task, never silently truncated
source. Missing inherited/helper bodies remain gaps. JARs provide names/signatures only;
no automatic decompilation or class initialization is performed. Private helpers are followed
from scoped calls; unresolved dispatch is reported rather than assumed equivalent.

## Generic request and result protocol

For automation use `compare --config CONFIG --request REQUEST_JSON --output REPORT_DIRECTORY`.
Paths in a request are relative to that request file. This schema has no format-library-specific
fields and works with unrelated Java projects:

```json
{
  "schema_version": "java-behavior-comparison-request-v1",
  "original": {"sources": ["original/src"], "dependency_sources": ["references/src"], "jars": ["lib/framework.jar"], "encoding": "UTF-8", "entry_methods": ["format", "unformat", "initializeFrom"]},
  "generated": {"sources": ["generated/src"], "dependency_sources": ["native-api/src"], "jars": [], "encoding": "UTF-8", "entry_methods": ["format", "unformat"]},
  "targets": [{"original_class": "example.Legacy", "generated_class": "example.Native"}]
}
```

Source/dependency locations accept Java files or directories. Optional entry_methods define
the compared entry contracts; constructors/fields and reached helpers remain included. Omitting
entry_methods reviews the selected classes' nonprivate source API. A scoped review never claims
that excluded public APIs are equivalent. Original and generated dependency catalogs stay separate.
Generated native API representation changes are analyzed explicitly; missing/null distinctions,
exceptions, aliasing, or context writes must not be normalized away to force agreement.

Stdout is one JSON report. Operational build output goes to stderr. Exit codes/decisions:
- 0 consistent_in_review: no differences identified within the completed selected static scope.
- 1 differences_found: at least one source-supported difference survived a second AI review.
- 2 inconclusive: missing evidence, unclear mapping, budget limits, or unresolved review tasks.
- 3 error: configuration, input or infrastructure failure; no acceptance decision is possible.

Every report states evidence_level=static_analysis. `complete` describes the selected workflow
scope, not semantic completeness or an equivalence proof. A difference decision may coexist
with incomplete coverage: confirmed-in-static-review findings do not mean everything was reviewed.

Reports contain input fingerprints, inspected file hashes, target pairs, findings, counterexample
proposals, remarks/suggested actions and source-location citations. `runs/<id>/report.md` is a short
human summary. `report.json` is the full machine result; `repair-feedback.json` is suitable to feed
back to an AI. `analysis.json` preserves inventories, mappings, scope and individual review results.
Raw stage requests/responses and validated cache receipts are under cache/tasks/. Sensitive source
is retained locally there; use an appropriate organization report directory.

## Resuming and limits

Rerun with the same output folder to resume accepted unchanged tasks. Source/config/prompt/code
identities determine run/cache reuse. Changed source invalidates affected task payloads, while
unaffected validated tasks can be reused. Raising time/call budgets does not invalidate model-task
results. One process owns an output folder at a time; after forcibly killing it, remove a stale
.comparison.lock only after verifying no comparison is still running.

The output directory must be outside input source directories. Inputs are hashed again at the end;
changed evidence invalidates the result. Symlinks are rejected. Parse/encoding warnings are recorded
in the index. Unrelated unreadable source does not hide valid targets, but unavailable target or
required dependency source prevents a completed positive review. Enclosing guards and exception
handlers stay attached to source members. Indexed fact accounting helps locate omissions; it is
not proof that the AI identified every behavior. Reverse and interaction checks are also heuristic.

API retries, task count, stage character limits, evidence expansion, interaction count, indexing
and AI-phase duration are bounded in config.yaml. Budget-exhausted work is reported as incomplete.
Cached work saves API calls; no automatic code repair or original/native execution is performed.
Use targeted execution-based comparison separately when stronger evidence is required.

## Tests

`python -m pytest tests -q` uses synthetic Java and scripted AI responses, including the actual
standalone HTTP client/CLI against a local test endpoint. It tests orchestration and evidence
handling, not the accuracy of a production model or universal behavioral equivalence.
