# GetCreditCardTransactions

---
entity_type: opStep
entity_id: GetCreditCardTransactions
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCreditCardTransactionsOp.xml
source_hash: 3d54389613ed4299ba00c8adfed40829bb530cdccb07fe2ad39532dcd88dd085
---

## Parent Operation
- [GetCreditCardTransactionsOp](operations/GetCreditCardTransactionsOp.md)

## Implementation
- [demo.bankcomposer.operations.cards.GetCreditCardTransactionsStep](classes/demo/bankcomposer/operations/cards/GetCreditCardTransactionsStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [GetCreditCardTransactionsNotFound](opsteps/GetCreditCardTransactionsNotFound.md)
- `on5Do` -> [GetCreditCardTransactionsInvalidRequest](opsteps/GetCreditCardTransactionsInvalidRequest.md)
- `onOtherDo` -> [GetCreditCardTransactionsFailed](opsteps/GetCreditCardTransactionsFailed.md)

## Raw Attributes
- entity: `card-transactions`
- id: `GetCreditCardTransactions`
- implClass: `demo.bankcomposer.operations.cards.GetCreditCardTransactionsStep`
- on0Do: `end`
- on4Do: `GetCreditCardTransactionsNotFound`
- on5Do: `GetCreditCardTransactionsInvalidRequest`
- onOtherDo: `GetCreditCardTransactionsFailed`
- sourceSystem: `cards`
