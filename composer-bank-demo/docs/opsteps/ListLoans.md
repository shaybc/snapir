# ListLoans

---
entity_type: opStep
entity_id: ListLoans
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\ListLoansOp.xml
source_hash: 8fe9ae738c75840af58c6834fb97f3f844414c117d5495fbf4aaf53944a75ab5
---

## Parent Operation
- [ListLoansOp](operations/ListLoansOp.md)

## Implementation
- [demo.bankcomposer.operations.loans.ListLoansStep](classes/demo/bankcomposer/operations/loans/ListLoansStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [ListLoansNotFound](opsteps/ListLoansNotFound.md)
- `on5Do` -> [ListLoansInvalidRequest](opsteps/ListLoansInvalidRequest.md)
- `onOtherDo` -> [ListLoansFailed](opsteps/ListLoansFailed.md)

## Raw Attributes
- entity: `loans`
- id: `ListLoans`
- implClass: `demo.bankcomposer.operations.loans.ListLoansStep`
- on0Do: `end`
- on4Do: `ListLoansNotFound`
- on5Do: `ListLoansInvalidRequest`
- onOtherDo: `ListLoansFailed`
- sourceSystem: `loans`
