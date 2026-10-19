# ValidatePin

---
entity_type: opStep
entity_id: ValidatePin
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Implementation
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)

## Parameters
- RequiredFields: `ClientId,Pin`

## Transitions
- `on0Do` -> [GetAccounts](opsteps/GetAccounts.md)
- `onOtherDo` -> [ValidationFailed](opsteps/ValidationFailed.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- RequiredFields: `ClientId,Pin`
- id: `ValidatePin`
- implClass: `com.ibm.il.dse.operations.common.ValidateInputFields`
- on0Do: `GetAccounts`
- onOtherDo: `ValidationFailed`
