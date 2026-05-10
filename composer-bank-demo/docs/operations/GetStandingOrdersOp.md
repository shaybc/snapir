# GetStandingOrdersOp

---
entity_type: operation
entity_id: GetStandingOrdersOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetStandingOrdersOp.xml
source_hash: ed60ccc46168e928c88fab3f8ddf342d27628fa34fadfc70153e43551d741cd7
---

## Context
- [GetStandingOrdersCtxt](contexts/GetStandingOrdersCtxt.md)

## Steps
- [GetStandingOrders](opsteps/GetStandingOrders.md)
- [GetStandingOrdersNotFound](opsteps/GetStandingOrdersNotFound.md)
- [GetStandingOrdersInvalidRequest](opsteps/GetStandingOrdersInvalidRequest.md)
- [GetStandingOrdersFailed](opsteps/GetStandingOrdersFailed.md)

## Formats
- csRequestFormat: [GetStandingOrdersRQFmt](formats/GetStandingOrdersRQFmt.md)
- csReplyFormat: [GetStandingOrdersRSFmt](formats/GetStandingOrdersRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.payments.GetStandingOrdersStep](classes/demo/bankcomposer/operations/payments/GetStandingOrdersStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  GetStandingOrders -->|on0Do| end
  GetStandingOrders -->|on4Do| GetStandingOrdersNotFound
  GetStandingOrders -->|on5Do| GetStandingOrdersInvalidRequest
  GetStandingOrders -->|onOtherDo| GetStandingOrdersFailed
  GetStandingOrdersNotFound -->|onOtherDo| end
  GetStandingOrdersInvalidRequest -->|onOtherDo| end
  GetStandingOrdersFailed -->|onOtherDo| end
```
