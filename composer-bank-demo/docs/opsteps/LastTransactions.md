# LastTransactions

---
entity_type: opStep
entity_id: LastTransactions
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\LastTransactionsOp.xml
source_hash: aa16b71c9ca816be36da91af5ef70ec46587489b3ffdf997690da6468cea536a
---

## Parent Operation
- [LastTransactionsOp](operations/LastTransactionsOp.md)

## Implementation
- [demo.bankcomposer.operations.accounts.LastTransactionsStep](classes/demo/bankcomposer/operations/accounts/LastTransactionsStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [LastTransactionsNotFound](opsteps/LastTransactionsNotFound.md)
- `on5Do` -> [LastTransactionsInvalidRequest](opsteps/LastTransactionsInvalidRequest.md)
- `onOtherDo` -> [LastTransactionsFailed](opsteps/LastTransactionsFailed.md)

## Raw Attributes
- entity: `transactions`
- id: `LastTransactions`
- implClass: `demo.bankcomposer.operations.accounts.LastTransactionsStep`
- on0Do: `end`
- on4Do: `LastTransactionsNotFound`
- on5Do: `LastTransactionsInvalidRequest`
- onOtherDo: `LastTransactionsFailed`
- sourceSystem: `core-banking`
