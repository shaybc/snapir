"""Instructions for source-derived obligations and material behavior comparison."""

POLICY = """Preserve source-established observable behavior for the same input, runtime context
and configuration: values, conditional branches, external-call arguments and ordering,
side effects, routing and errors. Preserve explicitly produced output names, structure,
prefixes, attributes and null/empty distinctions. Do not invent whitespace, ordering or
other exact-output obligations where the source does not establish them. Internal names,
formatting, helper structure and equivalent algorithms are not compatibility requirements.
This policy is an agreed requirement, not evidence that any specific source implements it."""

EXTRACT = """Extract observable behavior from the supplied XML/effective configuration and Java
implementations, parents and helpers BEFORE generating native code. Return schema JSON.
Use subject_scope to select reachable behavior of this configured unit or operation;
supporting sources can include unrelated methods which are not obligations of this task.
Each fact states its trigger and observable outcome, citing exact nonempty source excerpts
with supplied identities and hashes. Do not infer behavior from a tag/class name. Preserve
runtime-dependent conditions, both enabled/disabled branches and null/empty/nonempty cases
when evidenced. Describe external interactions and handling of returned values without
predicting live balances, dates or other changing data. Treat examples as examples only.
Separate source facts from agreed compatibility-policy facts. Do not cite policy text as
proof of an implementation. Leave fact_id empty; the runtime assigns stable IDs. Report
missing material evidence as unresolved_questions. Never invent a live value or require
human test data for behavior already established by source. When supplied only part of a
source, extract its evidenced facts and distinguish dependencies supplied in other parts
from genuinely absent evidence. This is an obligation list, not a proof of equivalence."""

RECONCILE = """Check all extracted facts and their exact original excerpts for cross-part
contradictions and missing material dependency behavior. Return conflicting_fact_ids and
unresolved_questions. Do not discard or rewrite facts, demand live service values, or flag
stylistic implementation preferences. Unseen source must not be guessed."""

COMPARE = """Review original evidence, source-linked behavior specification, generated Java
and tests. Return schema JSON with one finding per supplied fact, plus any source-grounded
behavior the extraction missed. Check the original excerpts rather than blindly trusting
the extracted interpretation. Use matched, missing, changed, invented_behavior or
insufficient_evidence; use non_behavioral_difference only for optional/style suggestions.
For every blocking mismatch provide original source citations, a concrete trigger and
observable consequence; cite actual candidate code where it exists. Missing implementation
may have no candidate location. Matched findings must cite candidate implementation, not
only tests. Non-behavioral differences never require regeneration. An unimplemented fact
cannot be dismissed as non_behavioral_difference. For additional omissions use no fact_id
and cite the original source. Report missing evidence specifically, not speculative risk.
Validate assertions against the original behavior too: a passing self-consistent test is
not proof. If review_scope limits tests, do not report other listed tests as missing.
Compilation alone does not prove equivalence. Return no prose outside schema JSON."""
