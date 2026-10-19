# ValidateTransfer

---
entity_type: opStep
entity_id: ValidateTransfer
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Implementation
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)

## Parameters
- RequiredFields: `SourceAccount,TargetAccount,Amount,Currency,SessionToken`

## Transitions
- `on0Do` -> [CheckLimits](opsteps/CheckLimits.md)
- `onOtherDo` -> [ValidationFailed](opsteps/ValidationFailed.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- RequiredFields: `SourceAccount,TargetAccount,Amount,Currency,SessionToken`
- id: `ValidateTransfer`
- implClass: `com.ibm.il.dse.operations.common.ValidateInputFields`
- on0Do: `CheckLimits`
- onOtherDo: `ValidationFailed`
