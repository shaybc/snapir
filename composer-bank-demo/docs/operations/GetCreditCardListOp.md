# GetCreditCardListOp

---
entity_type: operation
entity_id: GetCreditCardListOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCreditCardListOp.xml
source_hash: 5430b2c4ea5dc3d7a67ad02ebda88c0a49b4a8b21994c834927d2c772fdb4b0b
---

## Context
- [GetCreditCardListCtxt](contexts/GetCreditCardListCtxt.md)

## Steps
- [GetCreditCardList](opsteps/GetCreditCardList.md)
- [GetCreditCardListNotFound](opsteps/GetCreditCardListNotFound.md)
- [GetCreditCardListInvalidRequest](opsteps/GetCreditCardListInvalidRequest.md)
- [GetCreditCardListFailed](opsteps/GetCreditCardListFailed.md)

## Formats
- csRequestFormat: [GetCreditCardListRQFmt](formats/GetCreditCardListRQFmt.md)
- csReplyFormat: [GetCreditCardListRSFmt](formats/GetCreditCardListRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.cards.GetCreditCardListStep](classes/demo/bankcomposer/operations/cards/GetCreditCardListStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  GetCreditCardList -->|on0Do| end
  GetCreditCardList -->|on4Do| GetCreditCardListNotFound
  GetCreditCardList -->|on5Do| GetCreditCardListInvalidRequest
  GetCreditCardList -->|onOtherDo| GetCreditCardListFailed
  GetCreditCardListNotFound -->|onOtherDo| end
  GetCreditCardListInvalidRequest -->|onOtherDo| end
  GetCreditCardListFailed -->|onOtherDo| end
```
