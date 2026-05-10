# CreateLoanQuoteOp

---
entity_type: operation
entity_id: CreateLoanQuoteOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\CreateLoanQuoteOp.xml
source_hash: 680c4586cde79f10c42a7a175aa73ce472b12b971df8ea23c44407c40986d98a
---

## Context
- [CreateLoanQuoteCtxt](contexts/CreateLoanQuoteCtxt.md)

## Steps
- [CreateLoanQuote](opsteps/CreateLoanQuote.md)
- [CreateLoanQuoteNotFound](opsteps/CreateLoanQuoteNotFound.md)
- [CreateLoanQuoteInvalidRequest](opsteps/CreateLoanQuoteInvalidRequest.md)
- [CreateLoanQuoteFailed](opsteps/CreateLoanQuoteFailed.md)

## Formats
- csRequestFormat: [CreateLoanQuoteRQFmt](formats/CreateLoanQuoteRQFmt.md)
- csReplyFormat: [CreateLoanQuoteRSFmt](formats/CreateLoanQuoteRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.loans.CreateLoanQuoteStep](classes/demo/bankcomposer/operations/loans/CreateLoanQuoteStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  CreateLoanQuote -->|on0Do| end
  CreateLoanQuote -->|on4Do| CreateLoanQuoteNotFound
  CreateLoanQuote -->|on5Do| CreateLoanQuoteInvalidRequest
  CreateLoanQuote -->|onOtherDo| CreateLoanQuoteFailed
  CreateLoanQuoteNotFound -->|onOtherDo| end
  CreateLoanQuoteInvalidRequest -->|onOtherDo| end
  CreateLoanQuoteFailed -->|onOtherDo| end
```
