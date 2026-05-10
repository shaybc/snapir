# TransferFundsOp

---
entity_type: operation
entity_id: TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\TransferFundsOp.xml
source_hash: 8af31a020c8ccbb433962b9f974488492d5746089d39a314255515eeaec0dcc9
---

## Context
- [TransferFundsCtxt](contexts/TransferFundsCtxt.md)

## Steps
- [TransferFunds](opsteps/TransferFunds.md)
- [TransferFundsNotFound](opsteps/TransferFundsNotFound.md)
- [TransferFundsInvalidRequest](opsteps/TransferFundsInvalidRequest.md)
- [TransferFundsFailed](opsteps/TransferFundsFailed.md)

## Formats
- csRequestFormat: [TransferFundsRQFmt](formats/TransferFundsRQFmt.md)
- csReplyFormat: [TransferFundsRSFmt](formats/TransferFundsRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.payments.TransferFundsStep](classes/demo/bankcomposer/operations/payments/TransferFundsStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  TransferFunds -->|on0Do| end
  TransferFunds -->|on4Do| TransferFundsNotFound
  TransferFunds -->|on5Do| TransferFundsInvalidRequest
  TransferFunds -->|onOtherDo| TransferFundsFailed
  TransferFundsNotFound -->|onOtherDo| end
  TransferFundsInvalidRequest -->|onOtherDo| end
  TransferFundsFailed -->|onOtherDo| end
```
