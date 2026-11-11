# Codex working rules

## Prime directive: minimal scoped changes only

Codex must implement only the exact requested requirement.

Do not refactor, rename, reformat, optimize, clean up, reorganize, or simplify code unless the user explicitly asks for it.

Do not remove, change, or move existing behavior that is unrelated to the task.

Do not remove logging, comments, error handling, validation, telemetry, analytics, metrics, feature flags, backward compatibility code, or defensive checks unless the task explicitly requires it.

Preserve public APIs, method signatures, file structure, configuration, and existing behavior unless the requirement explicitly says to change them.

When modifying a file:
1. Identify the smallest code area needed for the requirement.
2. Change only that area.
3. Leave surrounding code untouched.
4. Preserve existing style and patterns in that file.
5. Do not perform opportunistic cleanup.

Before editing, write a short plan that includes:
- The exact files expected to change.
- The specific behavior being added/fixed.
- The areas that must not be touched.

After editing, provide:
- A summary of changed files.
- Why each changed file was necessary.
- Any behavior intentionally left unchanged.
- Confirmation that unrelated code was not modified.

If a requested change seems to require touching unrelated code, stop and explain why before making the change.

when asked to plan - give a detailed plan with code changes expected, add a section with the title: "Expected files to change:" and supply the files expected to change as a list of links.

When asked a question do not change code just answer and keep answers focused, concise, and directly responsive. Lead with the conclusion, then include only the essential supporting points. Avoid repetition, extensive background, diagrams, long task lists, and adjacent information unless explicitly requested. For general questions, stay under 50 lines whenever possible. If the subject requires a longer explanation, provide a short answer first and ask whether I want more detail. When researching, summarize the findings instead of reproducing the research.

## Ground code answers in reviewed evidence

When answering a question about this codebase's behavior, architecture, or execution flow, review the relevant code before drawing conclusions. You may rely on a code review already performed in the conversation when it directly covers the question and remains applicable to the current code. If that review is incomplete or may be outdated, inspect the missing or changed paths first.

Do not substitute guesses, generic expectations, statistical estimates, or assumptions for reviewing the implementation. Distinguish what the reviewed code establishes from what run-specific evidence proves. State any remaining uncertainty explicitly rather than presenting an unverified explanation as fact. Before claiming a capability or flow is absent, trace its implementation and callers, including applicable alternate and reuse paths.

## Check behavior across stages and phases

Whenever fixing behavior in one stage or phase, trace where that behavior is resolved, passed between stages, and consumed elsewhere. Check whether the same fix must also apply to other stages or phases, including preparation, analysis, conversion, validation, and resume/reuse paths. Do not assume that fixing one path fixes the others.

Update all applicable paths within the requested behavior's scope, preferably by reusing the same authoritative rule or resolved evidence rather than duplicating decisions. Add focused regression coverage for affected handoffs where appropriate. Before declaring the fix complete, report which other paths were checked and whether they required changes. Leave unrelated behavior untouched.

Apply a rule to another stage or phase only when it is applicable and correct for that stage's purpose and semantics. Checking consistency does not require identical behavior everywhere. Do not force a rule into stages where it does not belong; preserve intentional differences and explain why a checked stage needs no change.

<!-- a-ice:start -->
## Architecture model (a-ice)

This repository keeps a C4 architecture model in `.aice/`, drawn by the a-ice VS Code extension.
Before you create or edit anything in `.aice/`, read `.aice/agent/SKILL.md` and follow it.

- **Model in levels, top-down — never one flat list.** The top (Context) diagram shows only people, this codebase as one system, and external systems. Apps and data stores go *inside* the system, components *inside* the apps, and big components can hold sub-components. Every object with real internals gets children so the user can zoom into it. **Level 4 (sub-component) is the deepest:** never nest further; put finer detail in `details` and `code:`. See "Build the model in levels" in the skill.
- **Tags are for cross-cutting concerns, at most 3 per object.** Tag an object only for what is true of it, never with its children's tags, and never with tags that just repeat the structure. See "Tags" in the skill.
- **Respect the person's edits while they are true.** Fields listed in an object's or connection's `edited:` were written by a person: do not reword them for style, and keep them when the object only moves. When the code makes them wrong, correct them; when the object is replaced or gone, delete it with its customisations. Report every such change in your summary, and never clear `edited:`. See "Respect the person's edits" in the skill.
- **Keep the model in step with the code.** When a change adds, removes or renames a service, app, data store, queue, external integration, major module, or a call between them, update `.aice/model.yaml` (and any affected flow in `.aice/flows/`) in the same task. Pure refactors inside one module need no model change.
- **Check your work.** After editing the model, run `node .aice/agent/validate.cjs` and fix every error and warning it reports.
- **Show what the user asks for.** When the user asks to see, show or open part of the architecture, write `.aice/view.yaml` as described in the skill; the a-ice canvas jumps there.
- **Write the narrated tour.** When you create or change a diagram's content or a flow, write or update its `narration:` (what the narrator says at each stop). List the stops with `node .aice/agent/validate.cjs --tour <diagram or flow id>`. Keys in `narrationEdited:` are the person's: keep them while they are true, remove them when their stop is gone. See "Narrated tours" in the skill.
- Never edit layout positions in `.aice/diagrams/*.yaml`; a-ice owns them.
<!-- a-ice:end -->
