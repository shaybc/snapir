# ListLoansOp

---
entity_type: operation
entity_id: ListLoansOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\ListLoansOp.xml
source_hash: 8fe9ae738c75840af58c6834fb97f3f844414c117d5495fbf4aaf53944a75ab5
---

## Context
- [ListLoansCtxt](contexts/ListLoansCtxt.md)

## Steps
- [ListLoans](opsteps/ListLoans.md)
- [ListLoansNotFound](opsteps/ListLoansNotFound.md)
- [ListLoansInvalidRequest](opsteps/ListLoansInvalidRequest.md)
- [ListLoansFailed](opsteps/ListLoansFailed.md)

## Formats
- csRequestFormat: [ListLoansRQFmt](formats/ListLoansRQFmt.md)
- csReplyFormat: [ListLoansRSFmt](formats/ListLoansRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.loans.ListLoansStep](classes/demo/bankcomposer/operations/loans/ListLoansStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  ListLoans -->|on0Do| end
  ListLoans -->|on4Do| ListLoansNotFound
  ListLoans -->|on5Do| ListLoansInvalidRequest
  ListLoans -->|onOtherDo| ListLoansFailed
  ListLoansNotFound -->|onOtherDo| end
  ListLoansInvalidRequest -->|onOtherDo| end
  ListLoansFailed -->|onOtherDo| end
```
