# Bank operation-call end-to-end verification

**Result: failed conversion; live service-to-service verification was blocked.**

Run: `bank-operation-calls-e2e-20261019`
Profile: `configs/bank_operation_calls_validation.yaml`
Provider: Gemini; model: `gemini/gemini-3.5-flash-lite`; Java 25; native `behavior_units` conversion.

## What passed

- Real Composer Mapper discovery found Overview -> Validate -> Get Client Links, plus Overview -> Get Client Links directly.
- All ten original native units initially passed compilation, executable tests and behavior review.
- Get Client Links completed operation assembly, all four original routing scenarios and behavior review. Its database contract status is assembled, not deployed or validated as a packaged service.
- The final readiness-independent plan regenerated the three operation-call adapters. Validate -> Get Client Links and Overview -> Validate passed compilation, tests and review.
- The combined targeted converter regression suite passed: 98 tests, zero failures.

## Exact remaining blocker

The final Overview -> Get Client Links adapter, `configured_step-866cbe0670f145cea023b630`, exhausted its three current attempts. The first response omitted required native-operation-call coverage metadata, the second was invalid JSON, and the third omitted its own native interface contract.

Last error: `Unit response must declare its own native interface contract`.

Run status: `failed`; phase: `conversion_pending`. No executable service packages were produced.

## Live HTTP verification

The integration runner was executed and stopped at its package precondition: `Expected one executable service package for GetClientLinksOp`.
**Actual services started: 0. Actual HTTP requests completed: 0. No service-to-service success is claimed.**

The prepared runner checks all three public endpoints, saved downstream paths, XML request and response values, nested versus direct call counts and ordering, eight concurrent customers, database/no-links errors, and an unavailable downstream service. It records scenario failures rather than hiding them. Its Oracle JDBC procedure and lookup table are explicitly simulated; generated services and interservice HTTP calls are intended to be real. None of those live checks reached execution in this run.

## Scoped changes made while attempting the run

- `source/runtime/behavior_conversion/method_contracts.py`: Resolve declared nested Java member types consistently in native method contracts.
- `source/runtime/behavior_conversion/compiler_feedback.py`: Explain Mockito generic-return compiler errors, including saved feedback reused on resume.
- `source/runtime/behavior_conversion/route_test_plan.py`: Report invalid routing triples and the exact allowed original triples without relaxing routing validation.
- `source/runtime/behavior_conversion/operation_dependencies.py`: Accept requireNonNull message overloads while requiring the supplied step argument to be stored.
- `source/tools/conversion_tools/operation_call_closure.py`: Exclude mutable readiness status from caller API evidence; retain actual contract fingerprints and database readiness.
- `source/runtime/behavior_conversion/operation_calls.py`: Recognize a matching-base, slash-normalizing join of the saved HTTP path; reject wrong targets and wrong joins.
- `source/tests/runtime/test_method_contracts.py`: Regression coverage for nested member types and unrelated dollar identifiers.
- `source/tests/runtime/test_compiler_feedback.py`: Regression coverage for generic Mockito mismatch diagnostics and saved-feedback upgrades.
- `source/tests/runtime/test_operation_route_plan.py`: Regression coverage for exact routing-key correction diagnostics.
- `source/tests/runtime/test_operation_dependencies.py`: Regression coverage for null-check overloads and rejection of the wrong supplied role.
- `source/tests/test_operation_calls.py`: Regression coverage for readiness-independent caller evidence, real contract changes and normalized URL joins.
- `configs/bank_operation_calls_validation.yaml`: Isolated three-operation native conversion profile; existing profiles left unchanged.

Run-only integration artifacts: `integration/verify_calls.py`, `integration/FixtureDriver.java`, compiled fixture classes, and `integration/report.json`.

No hand edits were made to generated adapters or services. Existing bank operation definitions, existing profiles and unrelated application behavior were intentionally left unchanged. No commits, pushes or deployments were made.

## Reproduce

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='source'
python -m cli resume --config configs/bank_operation_calls_validation.yaml --run-id bank-operation-calls-e2e-20261019
```

Resume retains accepted work and grants the failed task another bounded correction window. It does not establish successful conversion or HTTP verification. The generator still needs to return a complete valid adapter contract before Validate and Overview assembly, packaging and the live test can finish.
