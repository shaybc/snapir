"""Convert one configured op-step with its helper evidence to native business code."""

from agents.behavior_conversion.native_instructions import native_instructions

INSTRUCTION = native_instructions("step") + """Return unit_contract with this unit_id, exact fully qualified public APIs matching the returned files, requirements and evidence_ids. Include input_type, output_type and wire_type where applicable. Generate typed data classes needed by this unit in the same bundle. dependency_units may name only supplied accepted units. Use the assigned native_package.
Implement one configured business step with the native APIs you declare in this response.
Use original implementation/helper source and XML attributes as behavior evidence. Replace
context access with typed arguments/results and replace Composer inheritance and service
lookup with declared collaborators. Merge small helpers where appropriate; retain database
and HTTP integration interfaces where required. Preserve calculations, return outcomes,
exceptions, configured values and side-effect order. Routing is owned by the enclosing service.
Reuse accepted dependency APIs without redefining them.
Include native companion implementations for supporting behavior required by this step
when it is not provided by a supplied accepted native API or a retained, declared ordinary
external dependency. Read the supporting source evidence and implement its required behavior
in this bundle, including integration collaborators and their helpers. Declare and wire
every generated collaborator consistently in implementation code, public API metadata and
tests. An interface or mock alone does not implement a required production collaborator.
Do not assume an original helper has already been migrated, invent a target package for it,
or fix a missing helper by importing its IBM source class. Before returning, check that
every required supporting type resolves to a returned native file, an accepted dependency
API or a declared ordinary library. Preserve unknowns explicitly rather than inventing behavior.
Return one valid JSON bundle matching schema, with main files and executable test files.
coverage maps every requirement ID to test file paths. Tests must check evidenced behavior
and side effects. Include evidence_ids and unresolved_questions; do not implement invented
defaults for unknown production behavior. Address correction_feedback, behavior_review_feedback and final_validation_feedback without changing the
approved interfaces. No Composer Context/router/formatter classes, TODOs, fences or POMs."""
