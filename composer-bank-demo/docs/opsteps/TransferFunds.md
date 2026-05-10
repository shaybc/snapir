# TransferFunds

---
entity_type: opStep
entity_id: TransferFunds
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\TransferFundsOp.xml
source_hash: 8af31a020c8ccbb433962b9f974488492d5746089d39a314255515eeaec0dcc9
---

## Parent Operation
- [TransferFundsOp](operations/TransferFundsOp.md)

## Implementation
- [demo.bankcomposer.operations.payments.TransferFundsStep](classes/demo/bankcomposer/operations/payments/TransferFundsStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [TransferFundsNotFound](opsteps/TransferFundsNotFound.md)
- `on5Do` -> [TransferFundsInvalidRequest](opsteps/TransferFundsInvalidRequest.md)
- `onOtherDo` -> [TransferFundsFailed](opsteps/TransferFundsFailed.md)

## Raw Attributes
- entity: `transfers`
- id: `TransferFunds`
- implClass: `demo.bankcomposer.operations.payments.TransferFundsStep`
- on0Do: `end`
- on4Do: `TransferFundsNotFound`
- on5Do: `TransferFundsInvalidRequest`
- onOtherDo: `TransferFundsFailed`
- sourceSystem: `payments`
