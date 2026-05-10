# PayBillOp

---
entity_type: operation
entity_id: PayBillOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\PayBillOp.xml
source_hash: 377916a9367cfa7c3a8a8871b876e418d65bc63b637e981cfe2fe9e34e33cdd9
---

## Context
- [PayBillCtxt](contexts/PayBillCtxt.md)

## Steps
- [PayBill](opsteps/PayBill.md)
- [PayBillNotFound](opsteps/PayBillNotFound.md)
- [PayBillInvalidRequest](opsteps/PayBillInvalidRequest.md)
- [PayBillFailed](opsteps/PayBillFailed.md)

## Formats
- csRequestFormat: [PayBillRQFmt](formats/PayBillRQFmt.md)
- csReplyFormat: [PayBillRSFmt](formats/PayBillRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.payments.PayBillStep](classes/demo/bankcomposer/operations/payments/PayBillStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  PayBill -->|on0Do| end
  PayBill -->|on4Do| PayBillNotFound
  PayBill -->|on5Do| PayBillInvalidRequest
  PayBill -->|onOtherDo| PayBillFailed
  PayBillNotFound -->|onOtherDo| end
  PayBillInvalidRequest -->|onOtherDo| end
  PayBillFailed -->|onOtherDo| end
```
