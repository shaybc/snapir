"""One mapping responsibility; no implementation, tests or contract regeneration."""
MAPPING='''Map only the assigned parser checklist IDs to the supplied current native code.
Return the exact task_revision, production_revision and batch_id. entries is a list of
ChecklistResponse objects: checklist_id, status=implemented, locations=[{path,excerpt}].
Locations may be anywhere in the supplied production evidence; one excerpt can support
several IDs, and one ID may have several locations. Excerpts must be exact nonempty code,
not comments, imports, package lines or invented signatures. Do not regenerate Java,
contracts, APIs, tests, dependencies or accepted sibling mappings. Return replacements
only for assigned IDs. Original/converted code need not have matching method structure.
If supplied evidence is insufficient, request exact evidence catalog IDs in evidence_requests;
the catalog groups exact declaration ranges by file owner, and every range has an evidence_id.
do not invent a mapping. An unresolved entry states a source-backed question, not proof
of a defect. Exclusions are allowed only when allow_exclusions is true and the existing
exclusion rules/authorizations support them. Citations establish traceability, not equivalence.
The errors array names ALL detectable previous defects and the correction needed per item.
No example IDs or illustrative business values are task data.'''

SEMANTICS='''Return only the semantic metadata schema. The application owns identities,
hashes, known dependencies, checklist mappings and actual Java method signatures. Select
exported api_types only from parsed APIs belonging to this target; do not export every
helper indiscriminately. Preserve typed selected boundaries and accepted prerequisite APIs.
Use api_members to select the supplied member IDs for entry/construction/accessor contracts
when a type also has unrelated public helpers. Never invent signatures or member IDs.
Describe only unresolved contract/binding/configuration semantics using exact supplied
evidence. Do not return checklist mappings, code, tests or Maven coordinates. Inherited
public methods already appear in parsed APIs; their parent implementations stay owned
by their prerequisites. State unresolved questions instead of inventing behavior.'''
