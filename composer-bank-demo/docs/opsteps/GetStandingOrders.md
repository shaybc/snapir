# GetStandingOrders

---
entity_type: opStep
entity_id: GetStandingOrders
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetStandingOrdersOp.xml
source_hash: ed60ccc46168e928c88fab3f8ddf342d27628fa34fadfc70153e43551d741cd7
---

## Parent Operation
- [GetStandingOrdersOp](operations/GetStandingOrdersOp.md)

## Implementation
- [demo.bankcomposer.operations.payments.GetStandingOrdersStep](classes/demo/bankcomposer/operations/payments/GetStandingOrdersStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [GetStandingOrdersNotFound](opsteps/GetStandingOrdersNotFound.md)
- `on5Do` -> [GetStandingOrdersInvalidRequest](opsteps/GetStandingOrdersInvalidRequest.md)
- `onOtherDo` -> [GetStandingOrdersFailed](opsteps/GetStandingOrdersFailed.md)

## Raw Attributes
- entity: `standing-orders`
- id: `GetStandingOrders`
- implClass: `demo.bankcomposer.operations.payments.GetStandingOrdersStep`
- on0Do: `end`
- on4Do: `GetStandingOrdersNotFound`
- on5Do: `GetStandingOrdersInvalidRequest`
- onOtherDo: `GetStandingOrdersFailed`
- sourceSystem: `payments`
