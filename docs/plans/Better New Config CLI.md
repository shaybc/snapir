# Better New Config CLI

Status: implemented on 2026-11-06.

## Goal

Make creation of a migration configuration understandable, reversible before saving,
and clearly separate from starting a migration. Apply the same experience through
`run.cmd` and `run-verbose.cmd`, which share the Python CLI.

The user must always know which configuration is being edited, what input is
required, how to go back, and whether the application is waiting or working.

## Current problem and evidence

- `configuration_wizard.prompt_text()` clears the terminal after each prompt.
  `select_option()` and `select_multiple()` also manage clearing independently.
  Prompt-toolkit screen restoration and leftover menu content can make the wizard
  appear to return to the main menu rather than advance to its next question.
- Long defaults appear inside the input label. The mapper JAR path can wrap onto
  multiple lines, hiding the fact that input is required.
- Choosing **Create a new map** records a choice; it does not start the mapper.
  The next question is the mapper JAR path, but that distinction is not explained.
- `create_configuration()` is a linear sequence with no Back action. It saves
  immediately after the last collected answer, without a final review screen.
- Creating a configuration already does not start a migration. Preserve this
  distinction rather than introducing automatic migration execution.

## Intended experience

### 1. Stable wizard presentation

Own rendering and navigation within the new-configuration wizard. Clear or redraw
at controlled section boundaries, then consistently render:

```text
Create configuration: huge_bank_demo
Section 2 of 9: Composer map
INPUT REQUIRED

Completed: Source workspace selected

Mapper JAR
Default:
  C:\GitHub\shaybc\snapir\source\composer-mapper\target\...

Press Enter to use this file, or enter another path.
Path >

Next: Enter answer   Back: Ctrl+B   Cancel: Esc
```

Show complete paths with terminal-width wrapping or on dedicated lines; do not
silently truncate the actual value. Support narrow terminals and plain text
without relying on color or Unicode symbols to convey state. Keep the main menu
out of the wizard view. Never clear redirected output or print terminal control
sequences to non-terminal streams.

Use **INPUT REQUIRED** only while waiting for the user. Use **WORKING** with the
named task only during real discovery, validation or saving. Preserve useful
validation errors on the current screen, next to the relevant answer.

Immediately after selecting **Create a new map**, display:

> A new map will be generated when you start a migration. No mapping is running
> now. Continue configuring the mapper below.

For an existing map, explain that selection checks the folder and full validation
occurs once when migration imports it. Preserve the existing validation policy.

### 2. Editable draft and configuration sections

Hold answers in memory until final confirmation. Suggested section order:

1. Configuration name and source workspace.
2. Composer map: create/reuse, mapper JAR or existing map folder.
3. Output folder.
4. Channels, operations and target languages.
5. Java version, JDK home and scanner inactivity timeout.
6. External dependency settings and conversion strategy.
7. Gate settings.
8. AI model connection settings.
9. Test and deployment settings.

Use existing collectors, defaults, model fields and validators. Do not introduce
another configuration schema or change the meaning of existing settings. Each
section edits a local copy; **Next** commits that section to the draft, while
**Back** discards unfinished edits in the current section and returns to the
previous section with its last committed answers prefilled. Explain this behavior
in the navigation help. The first section has no Back action.

Checkboxes must reopen with the draft's selections, not an empty selection or an
automatic selection of newly discovered operations. Preserve filtering and hidden
checked values. A text prompt's blank Enter retains the displayed value; optional
fields need an explicit, documented Clear action so they can actually be unset.

Provide visible **Next**, **Back**, and **Cancel** actions on selection screens.
Text prompts use Enter to accept, Ctrl+B to go back, and Esc to cancel; do not
reserve a literal text value such as `back`, which could be a legitimate answer.
Ctrl+C and EOF cancel safely. On leaving the draft, offer **Discard configuration**
or **Continue editing**, with no file written. Existing callers outside this wizard
must keep their current cancellation behavior.

### 3. Reconcile dependent choices

Changing an upstream answer must not leave stale, invisible downstream settings:

- Source workspace change: invalidate discovered channels/operations, rediscover
  on demand, retain only choices that still exist, and require scope review.
- Channel change: refresh available operations, preserve still-valid checks, show
  removals, and require confirmation of the resulting operation scope.
- Keep current operation-name selection semantics; do not redesign channel-qualified
  identities as part of this UX change.
- Map mode change: remove inactive-mode keys from the data being saved. Retain
  per-mode answers in the draft so toggling back restores them.
- Java version change: revalidate the selected JDK and request correction when it
  no longer matches. Do not silently keep an incompatible JDK.
- Config name change: recalculate the destination and overwrite requirement.
- Provider and other conditional changes: show applicable fields using current
  validation rules, and prevent stale hidden answers from overriding active choices.

Cache discovery only within an unchanged draft input set. Do not repeatedly scan
a huge source tree simply because the user visits Review or another section.
Show discovery activity for expensive work; do not start the Composer mapper,
Java dependency scanner, model calls or workspace intake during configuration.

### 4. Final review and explicit save

After all sections are complete, show **Review configuration: <name>**. Include:

- Destination configuration path and whether an existing file would be replaced.
- Source workspace, map create/reuse mode and relevant paths, and output folder.
- Channels, operation count and selected names, target languages and strategy.
- Java version/home, scanner inactivity timeout and external dependencies.
- Gate, model connection, test and deployment settings.

Summarize thousands of operations as counts and a bounded preview, with **View all
selected operations** and filtering/scrolling; do not print thousands of rows
before the final action. Display resolved paths alongside stored relative values
where that helps users verify the selection.

Show only the credential environment-variable name and set/unset status if useful;
never resolve or print its secret value. Sanitize credentials embedded in endpoint
URLs and other connection strings in summaries, errors and logs. Preserve the
existing environment-variable credential storage model.

Offer explicit actions:

1. **Save configuration** — validate and save the displayed draft.
2. **Edit a section** — select a section, edit its preserved answers, then return
   to Review, requiring dependent sections to be revisited where necessary.
3. **Back** — return to the last configuration section.
4. **Cancel** — confirm discarding the unsaved draft.

Do not make Save the initially focused review action; focus **Edit a section** so
an extra Enter after the last prompt cannot accidentally save. Clearly distinguish
normal advancement from final confirmation.

When replacing an existing configuration, confirm the exact destination after
Review and immediately before writing. Keep the current atomic save and
no-clobber behavior for new names; cancellation or validation failure must leave
an existing file unchanged. Validation errors return to the affected section
without discarding other answers. A destination collision must be presented as
a collision to resolve, never silently converted into overwrite permission.

After saving, display:

```text
Configuration saved: <path>
No mapping or migration has started.
Choose Start a new migration from the main menu when ready.
```

### 5. Separate confirmation for interactive migration start

Before an interactive **Start a new migration** invokes `run_pipeline()`, show a
concise summary of the chosen configuration, source workspace, map mode, output
root and selected scope. State that intake will begin and that a new map will be
generated during the run when applicable; do not promise an inaccurate stage order.

Offer **Start migration**, **Back to configuration selection**, and **Cancel**.
Initially focus Back. Returning to selection must preserve the previous choice
where possible. Cancel returns to the main menu without creating a run directory,
database or mapper process. Do not implicitly reopen a saved configuration for
editing here; the draft editing flow belongs to configuration creation.

Apply this confirmation only to interactive starts. Preserve explicit noninteractive
commands such as `python -m cli start --config ...` and their automation behavior.
Do not add confirmation prompts to Resume, status, gate decisions or other commands.

## Implementation approach

1. Add a small wizard draft model carrying section answers, current section,
   discovery cache keys and the review-return destination. Keep it independent of
   terminal rendering and persistent pipeline configuration.
2. Add wizard-scoped text/menu/checkbox adapters. They own screen headings,
   multiline defaults, prefilled answers and navigation signals. Prefer optional,
   backward-compatible extension points in existing input primitives rather than
   duplicating prompt-toolkit implementations. Existing callers retain defaults.
3. Add a section controller that invokes the existing collectors through adapters,
   commits section results, reconciles dependent fields and routes Back/Edit/Cancel.
   Existing collectors accept optional initial values only where necessary; avoid
   embedding navigation state into business validation code.
4. Make `create_configuration()` orchestrate the controller and review, retaining
   `configuration_path()`, `collect_path()` validation and `save_configuration()`
   as canonical entry points where applicable. Catch wizard-local navigation
   signals before they escape to the main CLI's global cancellation handler.
5. Implement bounded review formatting separately from navigation. Share sanitized
   configuration-summary formatting with the interactive start confirmation.
6. Wire interactive start confirmation just before `run_pipeline()` and before
   creating a run ID/directory. Keep launchers unchanged because both use this CLI.
7. Document controls and verify normal and verbose launchers in Windows terminals.

## Expected files to change:

Paths below are relative to this plan. New files are marked explicitly.

- [configuration_wizard.py](../../source/cli/configuration_wizard.py) — replace linear
  prompting with draft/section orchestration, review and explicit saving; preserve
  canonical path validation and atomic persistence.
- [configuration_draft.py](../../source/models/configuration_draft.py) **(new)** —
  transient draft state, per-section values and navigation state; no saved schema change.
- [configuration_flow.py](../../source/cli/configuration_flow.py) **(new)** — section
  sequencing, dependencies, draft commits and Back/Edit/Cancel handling.
- [configuration_inputs.py](../../source/cli/configuration_inputs.py) **(new)** —
  wizard-scoped prompt adapters, headings, multiline defaults and navigation controls.
- [configuration_review.py](../../source/cli/configuration_review.py) **(new)** —
  bounded, sanitized summaries and explicit final review actions.
- [migration_start_review.py](../../source/cli/migration_start_review.py) **(new)** —
  interactive-only start confirmation without creating run state.
- [interactive.py](../../source/cli/interactive.py) — optional initial menu selection,
  rendering/navigation hooks where needed; preserve existing default behavior.
- [multiselect.py](../../source/cli/multiselect.py) — optional initial checked values
  and wizard navigation hooks; preserve existing filtering and selection semantics.
- [terminal_display.py](../../source/cli/terminal_display.py) — minimal shared rendering
  support only if needed; retain redirected-output safeguards and unrelated callers.
- [composer_map_configuration.py](../../source/cli/composer_map_configuration.py) —
  accept existing draft answers and explain deferred map creation; keep validation policy.
- [java_configuration.py](../../source/cli/java_configuration.py) — prefill draft JDK
  and timeout answers, preserving validation and defaults.
- [external_dependency_settings.py](../../source/cli/external_dependency_settings.py) —
  accept previously entered section values without changing dependency rules.
- [gate_configuration.py](../../source/cli/gate_configuration.py) — preserve gate
  choices when revisiting the section.
- [model_configuration.py](../../source/cli/model_configuration.py) — preserve model
  connection choices and credential-variable handling.
- [test_deployment_settings.py](../../source/cli/test_deployment_settings.py) — preserve
  optional test/deployment choices during editing.
- [main.py](../../source/cli/main.py) — interactive start confirmation and local
  cancellation routing, leaving command-line automation unchanged.
- [test_configuration_wizard.py](../../source/tests/test_configuration_wizard.py) —
  draft navigation, final confirmation, validation and save/cancel regression coverage.
- [test_cli_interactive.py](../../source/tests/test_cli_interactive.py) — prefilled
  controls, interactive start routing and backward compatibility.
- [test_configuration_review.py](../../source/tests/test_configuration_review.py)
  **(new)** — bounded summaries, sensitive-value sanitization and screen formatting.
- [running_migrations.md](../running_migrations.md) — document navigation, explicit
  saving and the separate interactive start confirmation.

During implementation, verify existing tests/collector signatures before choosing
extension points. Limit each edit to the wizard requirement; do not restructure
unrelated CLI functionality or duplicate configuration validation.

## Validation and acceptance criteria

Automated checks should cover meaningful state transitions and side effects:

- Navigate back across every section; previous text and checkbox answers survive.
- Edit an early section from Review, return to Review, and reconcile its dependent
  choices without resetting unrelated answers or repeating unchanged discovery.
- Toggle new/existing map mode in both directions; inactive keys are not saved,
  active answers are restored, and no mapping/full-map validation is launched.
- Change Java version and source/channel scope; stale dependent choices cannot
  pass final validation silently.
- Confirm that Enter keeps defaults, optional values can be cleared explicitly,
  and Back/Cancel are distinct from literal input values.
- Review and cancellation perform no configuration write; only explicit Save
  calls persistence. Existing files survive cancellation, errors and name collisions.
- Confirm overwrite only after the final draft is reviewed; validate saved YAML
  through the existing model and loader.
- Test a narrow terminal, a very long mapper path and thousands of operation names:
  the input marker/actions remain visible and the review remains bounded.
- Ensure secrets never appear in review/error output, including URL userinfo and
  sensitive query parameters; environment-variable names remain usable.
- Interactive start Back/Cancel does not call `run_pipeline()` or create run state;
  explicit Start invokes it once with the reviewed profile. Noninteractive start
  keeps its existing behavior and has no new prompt.
- Existing menu, filtering, configuration-resolution and collector tests remain
  valid for callers that do not opt into wizard presentation/navigation.

Manually verify `run.cmd` and `run-verbose.cmd` in Windows Terminal and cmd.exe:
main-menu isolation, clear section headings, readable wrapped defaults, visible
input cursor, keyboard navigation, final review and the transition into real
working/progress output. Include `huge-bank-demo` with a single operation and a
large selection, without requiring full migration conversion for UX acceptance.

## Boundaries

Do not change saved configuration fields/defaults, existing config discovery,
conversion scope semantics, Composer-map validation frequency, mapper execution,
Java scanner timeouts, library counts, pipeline ordering, model behavior or gate
policies. Do not introduce persistent draft files or a new terminal framework.
Do not start migrations automatically after saving a configuration. Do not modify
generated demo folders or the currently running user's CLI process.

## Implementation record (2026-11-06)

Implemented the draft model, section controller, wizard input adapters, bounded
review, editable selections and separate interactive-start confirmation. Collector
answers are restored by the adapter using their existing prompt labels, avoiding
duplicate collectors or changes to saved configuration fields. The map, Java,
external-dependency and deployment collectors only needed credential-safe error
feedback; gate and model collectors and terminal-display helpers remained unchanged.
Both launch scripts continue to use the shared CLI without launcher edits.

The regression updates also include `test_cli_documentation.py` and
`test_cli_diagnostics.py` to account for the new interactive-start confirmation.
The related suite passed 148 tests. Two unrelated tests were excluded: the old
Bank Demo operation-list expectation and the test requiring the absent local
`configs/bank_demo.yaml`. Tests cover full draft editing and saving, cancellation,
dependency reconciliation, keyboard controls, 10,000-operation filtering, small
terminal rendering, redaction and noninteractive command compatibility.

An isolated Windows terminal session confirmed readable wrapped mapper paths,
visible input state and Edit as the default review action. It did not save a
configuration, invoke the mapper or start a migration. The user's existing CLI
process was not modified or controlled.
