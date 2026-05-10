# GetCreditCardTransactionsOp

---
entity_type: operation
entity_id: GetCreditCardTransactionsOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCreditCardTransactionsOp.xml
source_hash: 3d54389613ed4299ba00c8adfed40829bb530cdccb07fe2ad39532dcd88dd085
---

## Context
- [GetCreditCardTransactionsCtxt](contexts/GetCreditCardTransactionsCtxt.md)

## Steps
- [GetCreditCardTransactions](opsteps/GetCreditCardTransactions.md)
- [GetCreditCardTransactionsNotFound](opsteps/GetCreditCardTransactionsNotFound.md)
- [GetCreditCardTransactionsInvalidRequest](opsteps/GetCreditCardTransactionsInvalidRequest.md)
- [GetCreditCardTransactionsFailed](opsteps/GetCreditCardTransactionsFailed.md)

## Formats
- csRequestFormat: [GetCreditCardTransactionsRQFmt](formats/GetCreditCardTransactionsRQFmt.md)
- csReplyFormat: [GetCreditCardTransactionsRSFmt](formats/GetCreditCardTransactionsRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.cards.GetCreditCardTransactionsStep](classes/demo/bankcomposer/operations/cards/GetCreditCardTransactionsStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  GetCreditCardTransactions -->|on0Do| end
  GetCreditCardTransactions -->|on4Do| GetCreditCardTransactionsNotFound
  GetCreditCardTransactions -->|on5Do| GetCreditCardTransactionsInvalidRequest
  GetCreditCardTransactions -->|onOtherDo| GetCreditCardTransactionsFailed
  GetCreditCardTransactionsNotFound -->|onOtherDo| end
  GetCreditCardTransactionsInvalidRequest -->|onOtherDo| end
  GetCreditCardTransactionsFailed -->|onOtherDo| end
```
