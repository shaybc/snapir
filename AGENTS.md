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

## Check behavior across stages and phases

Whenever fixing behavior in one stage or phase, trace where that behavior is resolved, passed between stages, and consumed elsewhere. Check whether the same fix must also apply to other stages or phases, including preparation, analysis, conversion, validation, and resume/reuse paths. Do not assume that fixing one path fixes the others.

Update all applicable paths within the requested behavior's scope, preferably by reusing the same authoritative rule or resolved evidence rather than duplicating decisions. Add focused regression coverage for affected handoffs where appropriate. Before declaring the fix complete, report which other paths were checked and whether they required changes. Leave unrelated behavior untouched.

Apply a rule to another stage or phase only when it is applicable and correct for that stage's purpose and semantics. Checking consistency does not require identical behavior everywhere. Do not force a rule into stages where it does not belong; preserve intentional differences and explain why a checked stage needs no change.
