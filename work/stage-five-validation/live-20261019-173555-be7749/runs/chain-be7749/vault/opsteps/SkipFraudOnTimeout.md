# SkipFraudOnTimeout

---
entity_type: opStep
entity_id: SkipFraudOnTimeout
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Implementation
- [com.ibm.il.dse.operations.common.SetChannelContext](classes/com/ibm/il/dse/operations/common/SetChannelContext.md)

## Parameters
- FieldName: `FraudCheckSkipped`
- FieldValue: `true`

## Transitions
- `on0Do` -> [ExecuteTransfer](opsteps/ExecuteTransfer.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- FieldName: `FraudCheckSkipped`
- FieldValue: `true`
- id: `SkipFraudOnTimeout`
- implClass: `com.ibm.il.dse.operations.common.SetChannelContext`
- on0Do: `ExecuteTransfer`
- onOtherDo: `TechnicalError`
