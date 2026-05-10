# LastTransactionsOp

---
entity_type: operation
entity_id: LastTransactionsOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\LastTransactionsOp.xml
source_hash: aa16b71c9ca816be36da91af5ef70ec46587489b3ffdf997690da6468cea536a
---

## Context
- [LastTransactionsCtxt](contexts/LastTransactionsCtxt.md)

## Steps
- [LastTransactions](opsteps/LastTransactions.md)
- [LastTransactionsNotFound](opsteps/LastTransactionsNotFound.md)
- [LastTransactionsInvalidRequest](opsteps/LastTransactionsInvalidRequest.md)
- [LastTransactionsFailed](opsteps/LastTransactionsFailed.md)

## Formats
- csRequestFormat: [LastTransactionsRQFmt](formats/LastTransactionsRQFmt.md)
- csReplyFormat: [LastTransactionsRSFmt](formats/LastTransactionsRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.accounts.LastTransactionsStep](classes/demo/bankcomposer/operations/accounts/LastTransactionsStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  LastTransactions -->|on0Do| end
  LastTransactions -->|on4Do| LastTransactionsNotFound
  LastTransactions -->|on5Do| LastTransactionsInvalidRequest
  LastTransactions -->|onOtherDo| LastTransactionsFailed
  LastTransactionsNotFound -->|onOtherDo| end
  LastTransactionsInvalidRequest -->|onOtherDo| end
  LastTransactionsFailed -->|onOtherDo| end
```
