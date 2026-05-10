# GetAccountBalance

---
entity_type: opStep
entity_id: GetAccountBalance
source_file: C:\GitHub\shaybc\snapir\composer-bank-demo\operations\GetAccountBalanceOp.xml
source_hash: 6c67a7842ea0e345cd86387147cdac52b6b184732973b44b672cda2fd3737490
---

## Parent Operation
- [GetAccountBalanceOp](operations/GetAccountBalanceOp.md)

## Implementation
- [demo.bankcomposer.operations.accounts.GetAccountBalanceStep](classes/demo/bankcomposer/operations/accounts/GetAccountBalanceStep.md)

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [GetAccountBalanceNotFound](opsteps/GetAccountBalanceNotFound.md)
- `on5Do` -> [GetAccountBalanceInvalidRequest](opsteps/GetAccountBalanceInvalidRequest.md)
- `onOtherDo` -> [GetAccountBalanceFailed](opsteps/GetAccountBalanceFailed.md)

## Raw Attributes
- entity: `balances`
- id: `GetAccountBalance`
- implClass: `demo.bankcomposer.operations.accounts.GetAccountBalanceStep`
- on0Do: `end`
- on4Do: `GetAccountBalanceNotFound`
- on5Do: `GetAccountBalanceInvalidRequest`
- onOtherDo: `GetAccountBalanceFailed`
- sourceSystem: `core-banking`
