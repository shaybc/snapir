# GetCreditCardList

---
entity_type: opStep
entity_id: GetCreditCardList
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetCreditCardListOp.xml
source_hash: 5430b2c4ea5dc3d7a67ad02ebda88c0a49b4a8b21994c834927d2c772fdb4b0b
---

## Parent Operation
- [GetCreditCardListOp](operations/GetCreditCardListOp.md)

## Implementation
- [demo.bankcomposer.operations.cards.GetCreditCardListStep](classes/demo/bankcomposer/operations/cards/GetCreditCardListStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [GetCreditCardListNotFound](opsteps/GetCreditCardListNotFound.md)
- `on5Do` -> [GetCreditCardListInvalidRequest](opsteps/GetCreditCardListInvalidRequest.md)
- `onOtherDo` -> [GetCreditCardListFailed](opsteps/GetCreditCardListFailed.md)

## Raw Attributes
- entity: `cards`
- id: `GetCreditCardList`
- implClass: `demo.bankcomposer.operations.cards.GetCreditCardListStep`
- on0Do: `end`
- on4Do: `GetCreditCardListNotFound`
- on5Do: `GetCreditCardListInvalidRequest`
- onOtherDo: `GetCreditCardListFailed`
- sourceSystem: `cards`
