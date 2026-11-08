# CLI Configuration Map

This document lists the configuration wizards launched through `run.cmd` or
`run-verbose.cmd`. The first menu item, **Create Default Config**, selects the
current full conversion workflow. **Advanced Configuration** retains the previous
nine-step wizard documented below.

## Create Default Config

The wizard asks for these user inputs. It never starts mapping or conversion when saving.

1. Configuration name, source workspace and stable application/workspace ID.
2. Create a new indexed/scoped Composer map, or use an existing compatible indexed
   map. Supply the mapper JAR for a new map, or the map folder for reuse. Reused
   maps must have the same workspace ID; normal loader/source checks still apply.
3. Run output folder and persistent shared store folder (`../shared` by default).
4. Requested root channels and operations. Required dependencies are resolved
   automatically; Java is the fixed target language.
5. JDK version/home, scan inactivity timeout and Helm executable.
6. External dependencies, additional classpath JARs (JSON list), Eclipse classpath
   variables (JSON object), Maven settings and optional local repository.
7. Human or automatic approval policy and gate choices.
8. LiteLLM model, API endpoint and credential environment variable name. The
   defaults target Gemini Studio and `GEMINI_API_KEY`. Set the key in the process
   environment before saving; its value is never saved in the configuration.
9. Service environment, OpenShift namespace, cluster domain, service port,
   optional external URL pattern and exact `channel/operation` address overrides.

The external URL pattern supports `{service_name}`, `{namespace}`, `{channel}`
and `{operation}`, for example `https://{service_name}.apps.example.org`.
Address overrides can supply `internal_base_url`, `external_base_url`,
`service_name`, `namespace` and `service_port` (`port` is also accepted).
For example: `{"XML/ValidateClientOp":{"service_port":8081}}`. Unspecified
values inherit the selected environment convention.

The review shows these fixed settings, without offering older implementations:

| Setting | Fixed behavior |
| --- | --- |
| Conversion | Behavior units; components first; staged Java generation |
| Mapping | Indexed analysis and scoped layout |
| Shared reuse | Reuse compatible converted components across runs; use registered operation HTTP APIs |
| Tests and mocks | AI-generated shared fixtures and tests; compile and execute JUnit |
| Facts | Collection, checklist mapping and fact validation disabled |
| Format comparison | Enabled using executed tests and mocks; diagnostic facts disabled |
| Mutation tests | Enabled |
| AI behavior review | Enabled as an advisory review of source, code and tests; no fact collection |
| Output | Runnable standalone package and microservice generation |
| Helm validation | Required |
| AI provider | LiteLLM; no mock-provider or preparation-only choice |

`test_based_v1` is the supported fact-free readiness policy. It still requires
current source/settings/API evidence, passing compilation and executed tests.
It does not claim exhaustive behavioral equivalence. Historical experimental
facts-disabled receipts cannot satisfy this policy. Compatible shared candidates
are validated again in the current run before reuse.

Microservices use internal OpenShift service addresses for called operations.
Standalone packages use external addresses or explicit address overrides. A
missing namespace or external pattern can be left for later configuration;
deployment/readiness checks report incomplete addresses when needed. Saving the
configuration neither deploys services nor proves a remote service is running.
For a new microservice, the selected namespace, service name and port also seed
its `values.yaml`. The application/service port must be 1024–65535. Existing
`values.yaml` files retain user edits.

Editing sections, Back, cancellation, source-scope rediscovery and explicit
replacement confirmation use the existing wizard lifecycle. The advanced wizard
and existing saved profiles keep their previous behavior.

## Previous configuration wizard

An asterisk (`*`) marks the default value or initially highlighted menu choice.
Revisiting a section retains previous answers. Paths below assume the standard
repository layout and resolve relative to the saved configuration's folder.
Wizard defaults can differ from profile defaults when fields are omitted from YAML.

## 1. Name and source workspace

- **Configuration name:** free text; no default. Letters, numbers, underscores and
  hyphens are allowed. The wizard saves `configs/<name>.yaml`.
- **Source workspace:** any existing source folder.
  - `../bank-demo/composer/Workspace` *

## 2. Composer map

- **Map selection:**
  - Create a new map *
  - Use an existing map folder
- **When creating a new map — analysis format:**
  - Current map format *
  - Reusable AST index for large workspaces — scoped map
- **Mapper JAR:** any existing mapper JAR.
  - `../source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar` *
- **Workspace ID:** shown when creating a reusable AST index.
  - Configuration name *
  - Any other nonblank, stable workspace identifier
- **When using an existing map:** enter its folder; no default. Indexed maps supply
  their saved workspace ID automatically. The new-map and mapper-JAR prompts are
  skipped.

Choosing a new map records an action for migration startup. It does not run mapping
while the configuration wizard is open.

## 3. Output folder

- **Migration output folder:** any valid destination.
  - `../work/migration_runs` *

## 4. Channels, operations and languages

These are checkbox selections. **Nothing is checked initially.** “Select all” is an
available action, not an initial selection.

- **Channels:** discovered from the source workspace. Bank demo offers `INTERNET`,
  `IVR` and `XML`.
- **Operations:** discovered from the selected channels. Select individual
  operations or all operations. Filtering does not remove hidden selections.
- **Target languages:** Java is currently the only supported option.

At least one channel, operation and language must be selected. Required conversion
dependencies are resolved separately from these requested root selections.

## 5. Java and scanner timeout

- **Java version:**
  - `21`
  - `25` *
- **Java home:**
  - Automatically discovered matching JDK folder, when available *
  - Another installed matching JDK folder
- **Scanner inactivity timeout:**
  - `900` seconds *
  - Any positive whole number; progress resets the timer

Java home identifies the JDK folder, not its `bin` subfolder. The wizard validates
that the installation matches the selected Java version.

## 6. External dependencies and conversion strategy

- **External dependency rules:**
  - `[]` — no explicit rules *
  - A JSON list of rules
- **Each external dependency rule supports:**
  - Exactly one selector: `class_name` or `package_prefix`; no default selector
  - `treatment`: `retain` or `replace`; required, no default
  - `maven_coordinates`: optional; default `null` *
  - `behavior_description`: optional; default empty text *
  - `behavior_sections`: legacy compatibility field; default empty list *;
    excluded from serialized rules
- **Conversion strategy:**
  - `behavior_units` *
  - `legacy_components`

The wizard accepts the rules as one JSON field rather than individual rule screens.

## 7. Gate settings

- **Gate control:**
  - `human` *
  - `automatic`

This selection sets plan approval and all five gate policies. Automatic approval
still requires the relevant checks to pass. The wizard does not offer `skip` or
individual gate-policy editing.

## 8. AI model connection

- **Provider:**
  - `litellm` *
  - `gemini`
  - `mock`
- **Model name:**
  - `openai/your-model-name` * — placeholder
  - Any supported model identifier
- **Model base URL:**
  - `https://your-endpoint.example/v1` * — placeholder
  - The actual provider endpoint
- **Credential environment-variable name:**
  - `SNAPIR_LLM_API_KEY` *
  - Another environment-variable name

Selecting `mock` skips the remaining AI connection questions. The credential field
stores only the variable name, not the actual API key. The launching process must
have access to the variable's value.

For LiteLLM connected directly to Google AI Studio, use:

| Field | Value |
| --- | --- |
| Provider | `litellm` |
| Model | `gemini/<model-id-available-to-your-account>` |
| Base URL | `https://generativelanguage.googleapis.com` |
| Credential variable | `GEMINI_API_KEY` |

## 9. Test deployment

- **External test service base URL:**
  - `https://openshift/microservices/` * — placeholder
  - The actual HTTP/HTTPS base URL
  - Empty, by clearing the field with Ctrl+U
- **External service port:**
  - `auto` * — no explicit port override
  - A port from `1` to `65535`
- **Service hostname or route-path pattern:**
  - `ms_${ms_name}` *
  - Another pattern appropriate for the environment

These settings describe externally accessible test services. They do not deploy
services or establish that a server is running. Internal OpenShift service-address
settings are separate profile options.

## Final review

- Edit a section *
- Save configuration
- View all selected operations
- Back
- Cancel

Saving validates and writes the configuration. **It does not start migration.**
Replacing an existing configuration requires a separate replacement confirmation.
Choose **Start a new migration** from the main menu afterward.

## Navigation

- **Up/Down:** move between choices.
- **Space:** toggle a checkbox when its row is highlighted.
- **Enter:** accept a text answer or activate the highlighted menu action.
- **Next:** finish a checkbox screen or continue from a completed section.
- **Ctrl+U:** clear a text value; Enter alone otherwise retains its default.
- **Ctrl+B:** return to the previous section where supported.
- **Page Up/Page Down:** scroll review details; page through checkbox choices.
- **Esc/Ctrl+C:** request cancellation; unsaved drafts can be retained or discarded.

## Generation and validation settings missing from the wizard

These are YAML/profile settings, not additional wizard steps. This table covers the
generation and validation controls discussed here; **it is not the complete YAML
schema**.

| Setting | Available values | Default |
| --- | --- | --- |
| `scoped_native_mode` | `prepare`, `behavior_units_v1`, `component_first_v1` | `prepare` * |
| `test_preparation.mode` | `existing`, `ai_shared_fixtures_v1` | `existing` * |
| `executable_verification.mode` | `checklist_v1`, `executable_boundary_v1`, `conversion_checklist_v1` | `checklist_v1` * |
| `staged_unit_conversion` | `true`, `false` | `true` * |
| `cross_run_component_reuse` | `true`, `false` | `true` * |
| `format_comparison.enabled` | `true`, `false` | `false` * |
| `executable_verification.comparison_mutations.enabled` | `true`, `false` | `false` * |
| `unit_mutation_testing.enabled` | `true`, `false` | `true` * |
| `behavior_triage_enabled` | `true`, `false` | `false` * |
| `microservice.enabled` | `true`, `false` | `true` * |
| `microservice.require_helm_validation` | `true`, `false` | `true` * |
| `executable_verification.experimental_disable_facts` | `true`, `false` | `false` * |

The scoped preparation default applies to the scoped conversion path, not every
migration strategy. The default verification mode already performs validation.
Verification modes are alternatives, not independent switches that can all be
enabled together. Mutation and supplementary diagnostic results can be advisory;
their availability or score does not universally determine conversion acceptance.

When a run starts, omitted YAML settings receive profile defaults and the effective
profile is captured in the run's `state/profile.json`. Resume uses that captured
profile. Later edits to the originating YAML do not update an existing run.

## Implementation references

- [Wizard sections and field collection](../source/cli/configuration_flow.py)
- [Wizard navigation](../source/cli/configuration_inputs.py)
- [Checkbox selection](../source/cli/multiselect.py)
- [AI connection prompts](../source/cli/model_configuration.py)
- [Gate prompts](../source/cli/gate_configuration.py)
- [Profile fields and validation](../source/models/pipeline_configuration.py)
- [Central defaults](../source/constants.py)

## Detailed option explanations

The explanations below cover the options listed above. “Enabled” means a feature
is requested; it does not mean that its execution succeeded. Missing tools, inputs
or supported bindings can still prevent a check from completing.

There are three different kinds of result:

- **Required validation:** failures or incomplete evidence prevent the affected
  candidate or delivery from being accepted.
- **Approval:** a human or automatic policy decides whether to proceed after
  required checks pass. Approval does not override a failed technical check.
- **Advisory diagnostics:** findings are retained for inspection but do not, by
  themselves, reverse technical acceptance. A downstream feature can nevertheless
  require specific evidence produced by a diagnostic.

### Step 1: configuration name and source workspace

**Configuration name** identifies the YAML file, not a particular conversion run.
For example, `bank_live` produces `configs/bank_live.yaml`. Multiple separately
named runs can use that configuration. Changing the configuration name does not
rename old runs. Replacing an existing file requires confirmation.

**Source workspace** is the original Composer input: operation XML, registries,
formats, contexts, application Java and project metadata. It is not the generated
Java output folder or the Composer map. The selected folder must exist. Choosing
another source causes the wizard to require a fresh review of channel and operation
selections. Conversion still needs access to the original source for freshness
checks; having an old map alone is not permission to use changed source evidence.

### Step 2: Composer map and analysis

**Create a new map** schedules mapping when the migration starts. The mapper reads
source definitions and produces analysis evidence and navigable notes. Merely
choosing this option or saving the configuration does not perform mapping.

**Use an existing map folder** reuses a previously generated map after validation.
It avoids remapping, but does not waive source or map-integrity checks. Select the
map folder containing its manifest, not a migration's entire output folder. A map
for another workspace or source revision is not a compatible substitute.

**Current map format** uses the historical analysis path. This selection does not
opt into the reusable indexed/scoped path. It should not be interpreted as the
newest format merely because its menu label says “Current.”

**Reusable AST index for large workspaces** selects `indexed-v1` analysis and a
scoped map. AST means a parsed representation of Java syntax. The mapper retains
Java/XML facts in a disk-backed analysis store; converter intake loads the selected
operations and required dependencies from those facts. Mapping still analyzes the
workspace globally, which is necessary for dependency and sharing information.
This option enables an analysis/storage path, not AI generation. The scoped native
generation mode is a separate setting explained below.

**Mapper JAR** selects the built Java mapping tool. It does not select the AI model
or the target operation's generated JAR. A source checkout may need this tool built
before its JAR exists. The mapper requires its supported Java toolchain, currently
Java 25, even though generated application targets can be Java 21 or 25.

**Workspace ID** supplies a stable application identity for qualified source
definitions and reuse records. Keep it consistent for the same application across
runs and relocated checkouts. Give different applications different identities.
Changing the ID can change lookup identities; it does not migrate old registry
entries into the new identity. Indexed existing maps supply their recorded ID.

### Step 3: output folder

**Output folder** is the parent of separately named migration run directories.
Each run keeps its profile snapshot, database, map, generated projects, logs and
reports under its own directory. It is not the original source workspace.

Deleting this folder removes the runs stored there, including their ability to
resume. With default paths, approved reusable artifacts instead live in `shared/`.
Custom output and shared-store paths can place those files elsewhere.

### Step 4: channels, operations and target languages

**Channels** select the consuming environments of requested root operations.
Channel-specific mappings and overrides can affect the same XML-defined operation.
Selecting INTERNET is therefore not interchangeable with selecting XML. Necessary
imported definitions and dependencies can still come from other source projects;
the user need not select those projects as additional conversion roots.

**Operations** select the requested entry operations. Automatic dependency
resolution follows their qualified calls and required component evidence. An
available dependency can be prepared from source, or a compatible registered API
can satisfy an operation-call boundary. Required component artifacts are considered
for reuse under their existing validation rules. Missing or ambiguous evidence
still blocks. Selecting every operation increases conversion scope and AI/build
work; it is not necessary merely to include one operation's dependencies.

**Select all** checks the complete list. On the operation screen it includes
operations hidden by the current filter. **Filtering** only changes which rows are
visible; it does not deselect hidden rows. Check the selected count before Next.

**Target language** identifies the generated application language. Only Java is
currently offered. Selecting Java does not retain the Composer runtime engine;
the native path generates ordinary Java implementations and their required support.

### Step 5: Java target, installation and timeout

**Java version** sets the generated application's target version. Java 21 and 25
are separate targets; dependencies and generated builds must support the chosen
version. A different target can invalidate reusable build evidence. It does not
change the original Composer source's declared language version.

**Java home** identifies the matching installed JDK, including `java` and `javac`.
The converter supplies that toolchain to its Java/Maven processes. Merely typing
a folder does not install a JDK. A Java runtime without the compiler is insufficient.

**Scanner inactivity timeout** limits how long a Java analysis process may produce
no progress before it is treated as stalled. It is not the maximum total migration
time or the model request timeout. Progress resets the inactivity timer. Increasing
it permits longer quiet periods; it does not repair a stuck scanner or missing
dependency. Decreasing it can stop a valid but slow analysis prematurely.

### Step 6: external dependency declarations and conversion strategy

**No external dependency rules (`[]`)** means no explicit retain/replace decisions
are supplied through this field. Normal source discovery and dependency checks
still run. It does not mean “ignore external dependencies.”

**Class selector (`class_name`)** targets one exact Java class. **Package selector
(`package_prefix`)** declares a package boundary. Each rule must use exactly one
selector so the intended match is unambiguous.

**Retain** declares that a matched dependency is to remain an external dependency
rather than have its implementation converted. The converter still needs usable
classpath/artifact evidence and applies its allowed-class/artifact policy. This
does not universally permit retaining prohibited Composer runtime infrastructure.

**Replace** declares that matched behavior needs a native replacement rather than
retention of the original implementation. It supplies migration intent, not proof
that a correct replacement has already been generated. Source, documented behavior,
configuration and applicable validation still determine whether conversion can pass.

**Maven coordinates** identify the proposed retained library, conventionally
`groupId:artifactId:version`. They do not download a library merely while editing
the wizard and do not prove that it contains a required API. Resolution and managed
build checks remain responsible for validating dependencies.

**Behavior description** provides explanatory behavior context for a replacement.
It does not bypass code, API or executed-test checks. **Behavior sections** is a
compatibility input field rather than a normal separately prompted choice; it is
excluded from serialized rules.

**`legacy_components`** selects the older component-oriented conversion strategy.
It uses its existing closure, conversion, review and assembly flow. Selecting it
does not enable the component-first scoped capability.

**`behavior_units`** converts effective configured steps and complete request/reply
formats into native units, then assembles operations from accepted units. Base
class reuse and component-first execution are controlled separately. This strategy
alone does not override a scoped run's `prepare` mode.

### Step 7: approval policies

**Human** pauses at an approval point once its technical checks allow review. The
user inspects the report, records approval or rejection and resumes. Approving a
gate does not itself resume execution. Decisions bind to the reviewed report;
changed evidence can require another decision.

**Automatic** approves the gate when its required checks pass and continues where
the workflow permits. Failed checks still produce a blocker. It does not fabricate
an AI review, make incomplete evidence successful, deploy a service, or disable
validation. The wizard applies this one choice to plan approval and Gates 1–5.

The gates cover intake/dependency planning, component review, operation assembly
review, microservice creation approval and final delivery review. Their detailed
reports determine what is being approved. The plan approval policy is also separate
from the numbered gates, although the wizard assigns the same selected policy.

### Step 8: AI connection

**`litellm`** uses the embedded LiteLLM integration to call the provider identified
by the model prefix and endpoint. For Google AI Studio, use a `gemini/` model
identifier and the Gemini API endpoint. Selecting LiteLLM does not require starting
a separate LiteLLM proxy server for this direct-provider configuration.

**`gemini`** uses the native Gemini integration instead of the LiteLLM route. Both
can use a Google AI Studio key, but they are different client integrations.

**`mock`** selects deterministic fixture-based model execution. It is useful for
controlled tests and preparation checks. It is not a live AI conversion and does
not invent valid Java, fixtures or approval for arbitrary operations. Unsupported
mock tasks require actual fixtures or fail.

**Model name** selects the actual model. Prefixes matter when using LiteLLM:
`gemini/<id>` identifies Google AI Studio routing. The configured model must exist
and be available to the supplied account. A model name does not establish context
capacity, quota or successful connectivity; a real request is needed to test those.

**Model base URL** identifies the provider endpoint or an explicitly configured
gateway. For direct LiteLLM-to-AI-Studio calls, the base is
`https://generativelanguage.googleapis.com`. Placeholder URLs in the wizard must
be replaced for live execution.

**Credential variable name** tells the application which process environment
variable contains the key. For example, `GEMINI_API_KEY` is a name; the secret value
belongs in that variable. A launcher inherits its parent terminal's environment.
Changing a variable in another already-open terminal does not update a running
converter process. Credentials are not stored as key values in the YAML/profile.

### Step 9: test deployment addresses

**External test service base URL** describes a server reachable from the machine
running external tests or standalone calls. It is not evidence that the service
has been deployed. An empty value leaves that external address unfinished; it
does not disable every local compilation or package test. Calls needing the address
still require a real runtime configuration.

**External service port `auto`** leaves the URL's existing port, or the protocol's
default, in effect. A numeric value explicitly overrides the external port. This
is distinct from a Kubernetes Service's internal port.

**Route pattern** supplies the per-service hostname/path naming convention, using
the service-name placeholder where appropriate. It describes the actual routing
arrangement; it does not create Routes or services. Use the pattern expected by
the configured base URL and test infrastructure.

**Internal versus external addresses:** microservice callers use internal Service
addresses; standalone callers use external addresses. Namespace, service names,
cluster domain and explicit address overrides are separate profile/deployment
settings. The external test URL is not a universal substitute for internal DNS.

### Review, saving and captured profiles

**Edit a section** returns to an existing section and preserves committed answers.
**View all selected operations** lets the user inspect the full selection rather
than just the preview. Neither action starts conversion.

**Save configuration** validates and writes the YAML. It does not create a run or
call AI for conversion. **Back** returns to editing. **Cancel** offers draft
discard/continue behavior without silently saving partial configuration.

**Start a new migration** is a separate main-menu action. It creates a uniquely
named run and captures the resolved profile. **Resume a migration** reads the
captured profile and continues from retained evidence. Editing the original YAML
later does not change that snapshot or reset retry budgets. Use a new run when
testing a different conversion policy; do not manually rewrite saved evidence to
make an old run appear compatible.

### Scoped native generation mode

Field: `scoped_native_mode`. This applies specifically to scoped conversion.

- **`prepare` *:** resolve and inspect qualified operation/component dependencies,
  contracts and conversion inputs, then stop before native AI code generation.
  Preparation success does not prove generated code compiles or behaves correctly.
- **`behavior_units_v1`:** enable the scoped native unit-generation path, including
  its reviews, compilation, tests and operation assembly. It does not run the
  component-first generation phase. Some later features expect component-first
  evidence; selecting this mode does not manufacture those records.
- **`component_first_v1`:** generate or reuse required component implementations
  first, validate configured components, and assemble/verify units and operations
  using the accepted component APIs. It supports the shared component reuse flow.
  It can proceed to wrappers and final delivery when their checks and gates pass.

None of these values means that failed source resolution or required checks may
be ignored. The preparation-only default predates the cross-run dependency changes;
it is not a global switch disabling all older migration paths.

### Test preparation mode

Field: `test_preparation.mode`.

- **`existing` *:** keep the original test-preparation flow. This does not globally
  turn off AI implementation or all AI-generated tests; it does not opt into the
  separate shared fixture-bank/scenario preparation stages.
- **`ai_shared_fixtures_v1`:** use bounded AI tasks to prepare a retained fixture
  bank, JUnit scenarios and, where applicable, comparison scenarios. Generated
  artifacts are validated and associated with their source, configuration and
  candidate. They provide concrete test inputs rather than treating model claims
  as test results. The resulting Java/tests still have to execute successfully.

This is different from choosing the `mock` model provider. A fixture is test data
or a controlled dependency response; it is not necessarily a mocked AI response.
Unsupported or missing fixture semantics remain visible gaps. The setting does
not make a real database or deployed service available.

### Verification policy

Field: `executable_verification.mode`. These are alternative policies, not three
independent enabled/disabled switches.

| Mode | What it checks | What its success means |
| --- | --- | --- |
| `checklist_v1` * | Parser-derived obligations, candidate checklist mappings, API/settings checks, managed compilation/JUnit and supported isolated original/native boundary comparisons. | The required checks of this policy passed for the covered boundaries. It is not a proof of every possible execution. |
| `executable_boundary_v1` | Structured executable inputs, native invocation/API/settings checks, original/native execution and required coverage under the selected limits. It does not require the alternative AI checklist-citation format. | Required executable comparisons and coverage succeeded for the supported boundary and cases. Missing adapters or coverage can leave verification incomplete. |
| `conversion_checklist_v1` | Conversion mappings, source/configuration/API checks, compilation and executed JUnit. It does not require paired original/native boundary execution for acceptance. | Conversion readiness; behavioral equivalence is explicitly not assessed by this policy. |

Generating a test, compiling Java, comparing outputs and mapping facts are different
activities. A passing result in one is not automatically a passing result in all
the others. Branch-coverage requirements concern the supported comparison boundary;
they do not establish complete system-wide business coverage.

### Staged conversion

Field: `staged_unit_conversion`; default `true` *.

- **Enabled:** separate narrow tasks for implementation, metadata/API discovery,
  tests and dependency proposals. Production code is compiled before later stages,
  and bounded feedback is retained so tests-only corrections do not silently
  rewrite accepted implementation logic.
- **Disabled:** request the older combined-bundle route where that execution path
  permits it. It does not mean code generation, compilation or tests are disabled.

Both executable-boundary and conversion-checklist policies require staged
conversion. In addition, the live scoped runner currently forces staged conversion
when it constructs its own model executor. Therefore `false` is not a reliable
way to force unstaged live scoped conversion; some deterministic test entry points
can use the older route with an explicitly supplied model callback.

### Cross-run component reuse

Field: `cross_run_component_reuse`; default `true` *.

- **Enabled:** the eligible neutral component path looks for a compatible approved
  artifact before asking AI to implement it. Matching includes source resolution,
  relevant requirements/policy, target Java and dependency evidence. Reused code
  still receives current-scope validation and real builds/tests. Eligible accepted
  results can be retained in the shared store for later runs.
- **Disabled:** bypass that shared neutral-component lookup/publication route and
  generate through the normal candidate path. Other within-run reuse or separately
  implemented reuse mechanisms are not universally disabled by this one flag.

Configured occurrences and base implementations are different: reusing a base
formatter does not make every differently configured format occurrence accepted.
This flag also does not control registered operation REST API reuse. Missing or
corrupt artifacts are not trusted hits. Experimental fact-disabled results do not
enter the normal reusable-component path.

### Additional Format Comparison

Field: `format_comparison.enabled`; default `false` *.

**Purpose:** run additional diagnostics on a complete configured format after its
normal candidate checks. A request formatter's unformat direction reads XML into
logical context values. A response formatter's format direction writes XML from
those values.

- **Enabled:** prepare or reuse invocation bindings and test inputs, run the
  original format and converted format in Java, and compare observed results.
  Supported cases can compare XML, context effects and exception outcomes. With
  shared AI test preparation enabled, the diagnostic consumes its retained fixture
  bank and comparison scenarios. Otherwise bounded discovery can help propose
  bindings/context, and the converter prepares exploratory cases.
- **Disabled:** omit this supplementary format-diagnostic facility. The selected
  unit verification policy, compilation, JUnit and its required comparisons remain
  in force. This flag does not disable all format validation.
- **Acceptance effect:** the diagnostic reports `acceptance_changed=false`. It does
  not itself grant acceptance, regenerate Java, or turn an unavailable comparison
  into success. Preparation/execution errors can be recorded as
  `comparison_unavailable` for inspection.

**It is not simply “extract facts and compare the facts.”** Its central comparison
executes original and converted code against concrete inputs. Fact collection is
a separate control described next.

**Downstream dependency:** the current standalone sample writer needs a successful,
non-exception request-format fixture and matching comparison evidence. Disabling
this diagnostic, or enabling it without obtaining that evidence, can therefore
leave later sample creation unable to finish. Its advisory status does not mean
that every downstream consumer can operate without its output. The earlier
numeric-only integration fixtures fail at that sample requirement; they do not
represent a complete Composer XML request-format test.

#### Fact collection within format diagnostics

Field: `format_comparison.collect_facts`; default `true` *.

- **Enabled:** collect parser checklist facts and fact-derived branch probes for
  the diagnostic, alongside its actual execution and comparison work.
- **Disabled:** skip that diagnostic fact/probe collection and label it as disabled
  for testing. Entry discovery, source freshness and supported compilation/execution
  comparisons remain. This is not the global fact-disable experiment and does not
  change the selected converter-wide fact/mapping policy.

Other format-diagnostic controls are:

| Field | Default | Meaning |
| --- | --- | --- |
| `max_cases` | `64` * | Maximum comparison cases for this diagnostic; valid range 1–512. A cap is not proof of exhaustive coverage. |
| `case_timeout_seconds` | `15` * | Time limit for an individual diagnostic case; valid range greater than 0 through 120. A timeout is not a match. |
| `discovery_request_chars` | `900000` * | Character budget for context/binding discovery requests; valid range 1000–900000. It is not a guarantee that the selected model accepts a request of that size. |
| `compare_exception_messages` | `false` * | When enabled, include exception-message comparison; when disabled, exact message-text equality is not required by that comparison option. Other exception/failure semantics remain subject to the comparison implementation. |

### Comparison mutation diagnostics

Field: `executable_verification.comparison_mutations.enabled`; default `false` *.

- **Enabled:** on the executable-boundary path, introduce bounded deliberate
  changes into disposable candidate snapshots and rerun comparisons. This measures
  whether the comparison cases detect those changes. A surviving mutation suggests
  a gap in those cases; it is not a change published to the converted application.
- **Disabled:** omit this supplementary mutation measurement. Baseline required
  original/native comparison remains active under the selected verification policy.
- **Acceptance effect:** advisory. Survivor counts, worker failures and timeouts
  are reported without changing the production acceptance decision.

This option is connected to executable-boundary verification; setting it to true
does not make the other verification modes execute that path. Its default maximum
is four mutants and its default total worker timeout is 600 seconds. These settings
are independent of model retries and of PIT testing below.

### Unit mutation testing — PIT

Field: `unit_mutation_testing.enabled`; default `true` *.

- **Enabled:** on the applicable technically accepted unit path, run PIT against a
  retained disposable Java project to measure how well executable tests detect
  altered code. This tests test strength, not just whether the unchanged code passes.
- **Disabled:** skip this PIT measurement. Normal compilation, JUnit and required
  boundary checks are not thereby disabled.
- **Acceptance effect:** advisory. A low score, unavailable plugin or timeout does
  not independently fail an accepted unit. Inspect the test-strength report.

The default timeout is 180 seconds and the recommended score is 80. The recommended
score is not a mandatory acceptance threshold. Conversion-checklist mode does not
run the post-acceptance measurement used by the comparison-based unit path, even
if this setting is true.

### Additional AI behavior triage

Field: `behavior_triage_enabled`; default `false` *.

- **Enabled:** request an additional AI behavior review after technical unit
  verification, using original evidence, generated code and technical results.
  This adds model work and can help identify concerns worth investigating.
- **Disabled:** omit that extra review request. It does not turn off AI code
  generation or every review elsewhere in the workflow.
- **Acceptance effect:** this supplemental triage call is not the technical unit
  acceptance gate. Its execution errors are logged without invalidating the
  technical receipt. A model opinion is not an executed equivalence test.

### Microservice generation

Field: `microservice.enabled`; default `true` *.

- **Enabled:** after native operation acceptance and the applicable approvals,
  create and validate the Spring Boot wrapper, its project structure, deployment
  descriptors and Helm package. Gate 4 controls creation after Gate 3; Gate 5
  reviews final delivery. Native code and its retained tests remain inputs.
- **Disabled:** omit this optional native microservice-wrapper route and retain the
  existing service-generation path without its Gate 4. This is not a switch that
  disables all operation conversion or automatically selects a standalone-only
  delivery contract for every older strategy.

Creating a microservice package does not build/publish a container image or deploy
it to OpenShift. Those are separate explicit actions with their own required
environment settings. Package validation cannot prove that a remote database or
called service is currently available.

### Required Helm validation

Field: `microservice.require_helm_validation`; default `true` *.

- **Enabled:** Helm validation is required for the wrapper's packaging result.
  The configured Helm executable must be usable and the relevant chart checks must
  pass. The packaging path includes chart rendering/validation against its pinned
  Kubernetes schema as applicable.
- **Disabled:** a missing or unsuccessful Helm validation result is not required
  for that packaging-pass condition. This weakens the chart-validation requirement;
  it does not disable Java/Maven checks or prove the chart deployable.

Keep this enabled when the intended acceptance includes a validated Helm package.
It does not install a chart into a cluster. `helm_executable` defaults to `helm`;
`kubernetes_version` defaults to `1.34.0` and selects the schema target rather than
discovering or upgrading a live cluster.

### Experimental disabling of facts

Field: `executable_verification.experimental_disable_facts`; default `false` *.

- **Disabled (`false`):** keep normal fact collection/mapping requirements for the
  selected verification policy. The alternative executable policy still has its
  own rules; this flag does not force every mode to use AI checklist citations.
- **Enabled (`true`):** explicitly opt into a facts-disabled experiment. This is
  permitted only with `conversion_checklist_v1`. It skips the experiment's parser
  fact collection and AI fact-mapping validation while retaining applicable source,
  configuration/API, compilation and executed-JUnit requirements.
- **Acceptance effect:** results are labeled experimental, with behavioral
  equivalence not assessed. They cannot satisfy ordinary normal-readiness receipts
  or normal cross-run component publication requirements.

This is a test/experiment control, not a shortcut for making a production validation
failure pass. It is different from disabling only diagnostic fact collection via
`format_comparison.collect_facts`.

### Reading “everything passed”

Overall completion, technical acceptance and supplementary diagnostic success must
be inspected separately. A completed migration can still have advisory diagnostics
that were unavailable, timed out or found weak tests. Conversely, a passing build
does not override an incomplete required boundary check or failed gate precondition.

Use the full native execution and final delivery reports to assess generation and
packaging. The scoped preparation report describes input readiness only. Inspect
format comparisons, test-strength and comparison-strength reports when those
diagnostics are part of the intended evaluation. A configured feature, an approved
gate and a deployed working service are three separate facts.

### Further implementation references for these explanations

- [Scoped mode dispatch](../source/runtime/scoped_native/runner.py)
- [Verification-policy selection](../source/runtime/behavior_conversion/verification_mode.py)
- [Required unit verification](../source/runtime/behavior_conversion/verification_ladder.py)
- [Shared AI test preparation](../source/runtime/test_assets/preparation.py)
- [Additional format diagnostics](../source/runtime/format_comparison/component_diagnostics.py)
- [Format diagnostic execution](../source/runtime/format_comparison/runner.py)
- [Standalone sample evidence requirements](../source/runtime/behavior_conversion/standalone_sample.py)
- [Shared component lookup and validation](../source/runtime/component_conversion/shared_reuse.py)
- [PIT test-strength measurement](../source/runtime/behavior_conversion/verification_test_strength.py)
- [Comparison mutation measurement](../source/runtime/behavior_conversion/comparison_strength.py)
- [Supplementary behavior review](../source/runtime/behavior_conversion/verification_units.py)
- [Approval checks](../source/runtime/human_gates.py)
