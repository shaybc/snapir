# PayBill

---
entity_type: opStep
entity_id: PayBill
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\PayBillOp.xml
source_hash: 377916a9367cfa7c3a8a8871b876e418d65bc63b637e981cfe2fe9e34e33cdd9
---

## Parent Operation
- [PayBillOp](operations/PayBillOp.md)

## Implementation
- [demo.bankcomposer.operations.payments.PayBillStep](classes/demo/bankcomposer/operations/payments/PayBillStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [PayBillNotFound](opsteps/PayBillNotFound.md)
- `on5Do` -> [PayBillInvalidRequest](opsteps/PayBillInvalidRequest.md)
- `onOtherDo` -> [PayBillFailed](opsteps/PayBillFailed.md)

## Raw Attributes
- entity: `bill-payments`
- id: `PayBill`
- implClass: `demo.bankcomposer.operations.payments.PayBillStep`
- on0Do: `end`
- on4Do: `PayBillNotFound`
- on5Do: `PayBillInvalidRequest`
- onOtherDo: `PayBillFailed`
- sourceSystem: `payments`
