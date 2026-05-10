# CreateLoanQuote

---
entity_type: opStep
entity_id: CreateLoanQuote
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\CreateLoanQuoteOp.xml
source_hash: 680c4586cde79f10c42a7a175aa73ce472b12b971df8ea23c44407c40986d98a
---

## Parent Operation
- [CreateLoanQuoteOp](operations/CreateLoanQuoteOp.md)

## Implementation
- [demo.bankcomposer.operations.loans.CreateLoanQuoteStep](classes/demo/bankcomposer/operations/loans/CreateLoanQuoteStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [CreateLoanQuoteNotFound](opsteps/CreateLoanQuoteNotFound.md)
- `on5Do` -> [CreateLoanQuoteInvalidRequest](opsteps/CreateLoanQuoteInvalidRequest.md)
- `onOtherDo` -> [CreateLoanQuoteFailed](opsteps/CreateLoanQuoteFailed.md)

## Raw Attributes
- entity: `loan-quotes`
- id: `CreateLoanQuote`
- implClass: `demo.bankcomposer.operations.loans.CreateLoanQuoteStep`
- on0Do: `end`
- on4Do: `CreateLoanQuoteNotFound`
- on5Do: `CreateLoanQuoteInvalidRequest`
- onOtherDo: `CreateLoanQuoteFailed`
- sourceSystem: `loans`
