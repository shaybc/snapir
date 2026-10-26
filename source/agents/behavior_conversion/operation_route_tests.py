"""Small implementation, route-planning and single-scenario operation tasks."""

IMPLEMENTATION = """Generate the provisional operation service: implementation main files only.
Return one NativeUnitBundle JSON object containing main Java sources and operation_contract.
No test files, test helpers, test dependencies, route-test plans or coverage metadata.
Compilation comes first; route planning and scenario tests are separate later requests.
Connect the supplied accepted native units using ordinary Java calls and branches.
Receive EVERY required_step_dependencies role as a public constructor argument, store it
in a distinct field and call that supplied object. Return step_dependencies metadata in
operation_contract: binding_id, unit_id, type_name, parameter_name, field_name.
Choose an existing accepted entry API type for each role; do not create replacement steps,
use hidden factories, static service locators or new step instances inside this service.
All public constructors must receive these required objects; no no-argument fallback.
The supplied constructor_example illustrates structure only, not business routing or types.
Stage six supplies real step objects through Spring; route tests supply mocks through the
same constructor. Keep test-specific switches and Spring annotations out of this service.
For each required_runtime_resources entry, receive its provider_type through the constructor
and describe it in operation_contract.runtime_resources with input_key, resource_type,
provider_type, parameter_name and field_name. Copy connection_id when supplied and keep
distinct connectors as distinct providers, including steps that use the same map input key.
For discovered service_connections, source connection ownership overrides the default below:
preserve regular per-step release versus transactional reuse and original commit/rollback scope.
Do not merge pools or assume every resource lasts for the whole operation.
For JDBC without a discovered ownership contract, receive javax.sql.DataSource; during
each execute call acquire a Connection with try-with-resources, put that same connection in
the existing input map under the exact input_key, and share it with the steps for that call.
Release it on success, failure and early return. Do not open connections in constructors or
invent deployment credentials. Preserve evidenced transaction/error behavior; do not invent
commit/rollback rules. Stage six configures the real DataSource from deployment properties.
Preserve original routing, timeout priority, initialization, channel filtering, error-body
switches, side-effect order and final steps. Do not create a Composer runtime, reflective
router or generic Context engine. No HTTP controller; wrappers follow operation review.
Include any required native companion implementation and operation data sources.
Reuse exact accepted APIs and sources as dependencies; never return their source files.
Derive each call's result type from its accepted method signature, not the method name
or a presumed wire-to-business pipeline. A method such as unformat may already return
the business input; use that result directly instead of assigning it to a wire DTO and
converting it again. Call a separate wire-to-business mapper only with its accepted input type.
Copy every accepted_units entry's contract into operation_contract.units exactly, including
all APIs, method_signatures, dependency_units, requirements, evidence_ids and schema fields.
Do not shorten these contracts to only the methods used by this service, omit DTO/wire APIs,
drop evidence IDs or rename fields. They are immutable application-owned metadata.
Declare the implemented service_api and evidenced business/wire input, success and error types.
For correction_feedback, compiler_correction, behavior_review_feedback or final_validation_feedback,
correct only the candidate main implementation and its matching operation metadata.
Discard test files from any earlier response; preserve accepted units and their full contracts.
Use source evidence for behavior; flag unresolved evidence rather than inventing defaults.
Return complete valid JSON with no prose or fences."""

IMPLEMENTATION_COMPILER = """When compiler_correction is supplied, correct the latest failed
main sources using its diagnostics and relevant_dependency_apis. Check calls against the
verified parameters and return types; do not invent methods or change accepted interfaces.
Include missing native companion implementations only when source evidence supports them.
Return the corrected main implementation and exact operation metadata, without tests.
Preserve evidenced business behavior; compiler diagnostics are not replacement business rules."""

SCENARIO_COMPILER = """When compiler_correction or test_correction is supplied, use its
diagnostics, failing assertion/setup and source evidence to correct only the assigned scenario
test file. Check actual accepted APIs rather than inventing calls. Preserve other passing tests.
Do not weaken assertions or change accepted production code or contracts. If production code
conflicts with evidenced behavior, report the defect in unresolved_questions for review.
Return exactly the assigned test file with valid JSON; the scenario is compiled and run again."""


def implementation_dependencies(java_version):
    """Supply dependency and Java rules without asking an implementation phase for tests."""
    return (f"All main implementation code and proposed dependencies must support Java {java_version}. "
            "Reuse known_dependencies coordinates, versions and scopes exactly. Declare only "
            "dependencies required by returned main sources. Test-scoped inventory entries are "
            "not main-code dependencies. Propose a pinned new dependency only when absent from "
            "that inventory and required by the implementation. Report compatibility conflicts "
            "in unresolved_questions rather than silently upgrading dependencies.")

PLAN = """Create a route-test plan, not code, using the original routing_graph and operation
configuration plus the compiled assembled service and accepted APIs. Identify scenarios
for every original outcome/error/timeout edge, terminal path and operation-flow obligation;
do not derive coverage solely from generated code, which might omit original behavior.
Return RouteTestPlan JSON. Each scenario describes inputs, collaborator setup, expected
observable outcome/side effects, exact covers requirement IDs and routes as original
source/outcome/target triples. Routes must form a continuous original path, starting at
the entry step and ending at a terminal target.
A scenario's assertion focus is not its execution boundary: it may assert one step's
behavior, but must still describe the complete operation execution to a terminal result.
Include collaborator setup and selected outcomes for every downstream step on that path.
A target that is another source key in routing_graph is an intermediate step, not terminal.
Do not stop merely because the focused assertion's step has finished or its next step is reached.
Before returning, trace each scenario from entry_step: every target must equal the next
edge's source until the last target is outside routing_graph. Check the full path and
expected final result against the original routing; never invent edges to complete it.
For example, with an original entry -> check -> execute -> end route, a scenario focused
on check must include entry -> check -> execute -> end, not just entry -> check -> execute.
This example is illustrative; use only the supplied operation's actual edges and outcomes.
Use multiple small scenarios rather than
one enormous test. Derive expected behavior from evidence, not invented defaults or the
current implementation alone. Flag discrepancies or unavailable evidence explicitly in
unresolved_questions. No Java, Markdown, fences or coverage file paths; the application
writes the human-readable Markdown plan and assembles coverage from accepted scenarios."""

SCENARIO = """Generate exactly one focused operation test for scenario, against assembled_code
and the supplied accepted APIs. Return NativeUnitBundle JSON with one Java test file at
expected_test_path. Use its assigned package and test class. No main files, service changes,
new unit implementations or operation_contract. Nested test helpers may live in this file.
Use the verified testing_contract, known dependency versions, configured Java version and
plain Mockito for external collaborators only.
Use operation_contract.step_dependencies to supply mocked step objects to the real service
constructor. Stub all step outcomes needed for the full scenario path. Run real operation
routing; mock the step objects that would call external systems, not the operation service.
No live JDBC, HTTP, mainframe or filesystem is needed for these route tests. If constructor
resource arguments are needed, supply mocks for them too rather than connecting to real systems.
Exercise the operation and assert the planned outcome, relevant calls and side effects; initialization-only or assertNotNull-only tests are
insufficient. Do not weaken assertions or invent expected behavior to match current code.
coverage is assigned by the application from scenario.covers, not generated by the model.
Preserve accepted interfaces and other tests. Explain unresolved evidence instead of guessing.
If the scenario reveals an implementation defect, report it as unresolved_questions; do not
silently rewrite production code. Corrections address only this scenario's candidate test.
Return one complete valid JSON response without prose or fences."""
