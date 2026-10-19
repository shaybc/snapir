# Conversion plan

Approval applies to this complete scope, order and dependency evidence.

| Order | Wave | Operation | Direct prerequisites |
|---|---|---|---|
| 1 | 1 | INTERNET/GetClientLinksOp |  |
| 2 | 2 | INTERNET/ValidateClientLinksOp | INTERNET/GetClientLinksOp |
| 3 | 3 | INTERNET/GetClientOverviewOp | INTERNET/GetClientLinksOp, INTERNET/ValidateClientLinksOp |

## Reused published services

None.

## Approval evidence

Full plan, graph, scope, reused API contracts and note hashes: [conversion_plan.json](conversion_plan.json).

Evidence fingerprint: `2bf81fcf9542e8d6ebc304e95d05860cd86e3df8be8b3700601d3b6621ec19d7`
