# Verified Java 25 testing template

The application supplies this template as requirement `java25-test-template`, version 1,
for native format, op-step and service generation targeting Java 25.

The authoritative dependency pins and rules live in
`runtime/behavior_conversion/testing_contract.py`. They are supplied to the model as
`testing_contract` and merged into its known dependency inventory.

- `BusinessBehaviorTest.java` illustrates small tests for returned values and collaborator calls.
- `AdapterContractTest.java` illustrates external API stubbing and adapter interaction assertions.

Derive actual inputs, expected outputs and side effects from the migration evidence.
Example class names, values and SQL are illustrative. Keep business tests and adapter
contract tests separate. Use the provided mocking API for external interfaces; narrow
interfaces generated for the application can have small local doubles.

The candidate builder verifies the platform dependencies and applies approved test-only
pins inside the disposable build. Ordinary production dependencies retain their conflict
policy. The canonical project is updated only after compilation and executed tests pass.

Adopting this requirement invalidates older applicable acceptance that lacks its version.
Future semantic testing-policy changes must advance the requirement version. Wording-only
clarifications do not require a version bump. The accepted source and behavior tests remain
subject to the existing validation and review gates.
