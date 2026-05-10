# GetAccountBalanceOp

---
entity_type: operation
entity_id: GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetAccountBalanceOp.xml
source_hash: 6c67a7842ea0e345cd86387147cdac52b6b184732973b44b672cda2fd3737490
---

## Context
- [GetAccountBalanceCtxt](contexts/GetAccountBalanceCtxt.md)

## Steps
- [GetAccountBalance](opsteps/GetAccountBalance.md)
- [GetAccountBalanceNotFound](opsteps/GetAccountBalanceNotFound.md)
- [GetAccountBalanceInvalidRequest](opsteps/GetAccountBalanceInvalidRequest.md)
- [GetAccountBalanceFailed](opsteps/GetAccountBalanceFailed.md)

## Formats
- csRequestFormat: [GetAccountBalanceRQFmt](formats/GetAccountBalanceRQFmt.md)
- csReplyFormat: [GetAccountBalanceRSFmt](formats/GetAccountBalanceRSFmt.md)

## Java Dependencies
- [demo.bankcomposer.operations.accounts.GetAccountBalanceStep](classes/demo/bankcomposer/operations/accounts/GetAccountBalanceStep.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)
- [demo.bankcomposer.operations.common.MapErrorByValueAlways](classes/demo/bankcomposer/operations/common/MapErrorByValueAlways.md)

## Flow Diagram
```mermaid
graph TD
  GetAccountBalance -->|on0Do| end
  GetAccountBalance -->|on4Do| GetAccountBalanceNotFound
  GetAccountBalance -->|on5Do| GetAccountBalanceInvalidRequest
  GetAccountBalance -->|onOtherDo| GetAccountBalanceFailed
  GetAccountBalanceNotFound -->|onOtherDo| end
  GetAccountBalanceInvalidRequest -->|onOtherDo| end
  GetAccountBalanceFailed -->|onOtherDo| end
```
