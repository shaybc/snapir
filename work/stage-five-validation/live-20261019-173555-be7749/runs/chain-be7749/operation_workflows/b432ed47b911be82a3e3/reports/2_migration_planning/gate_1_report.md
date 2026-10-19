# Gate One: Review the migration plan

Do you approve the selected operations, batch order, and proposed component ownership?
Approval accepts this plan as the basis for conversion.

## Migration scope

Selected channels: INTERNET

Requested operations: GetClientLinksOp

Excluded operations: None

Operations planned: 1; batches: 1.

## Batch 1 — Pilot: first conversion batch


Batch composition: distinct dependencies recorded for the selected operations
Totals count each definition or Java class once across this batch.

Component type | Count
---------------|------
Operation step definitions | 4
Format definitions | 3
Context definitions | 3
Formatter definitions | 17
Decorator definitions | 6
Java implementation classes | 10
Additional Java dependencies | 3

Additional Java dependencies are identified by static source analysis; inspect source for dynamic dependencies.

Operation | Target | Classification | Review
--- | --- | --- | ---
INTERNET / GetClientLinksOp | java | db bound | [Operation details](gate_1/operations/0001-INTERNET-GetClientLinksOp.md)

## Review and decision

Operations with blocked context dependencies: 0.

[Review shared-library decisions](gate_1/shared_libraries.md)

Review the scope and batch order above, each operation's dependencies and outcomes, and shared-library ownership.

Choose **Approve a gate** to accept the proposal, then **Resume a migration** to continue. Choose **Reject a gate** if changes or further evidence are needed.

Approval policy: automatic.

Your decision is bound to the overview and all linked reports.
