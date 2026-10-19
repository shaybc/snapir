# ValidateRequest

---
entity_type: opStep
entity_id: ValidateRequest
conversion_status: not_started
used_by_operations:
  - GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
---

## Implementation
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)

## Parameters
- RequiredFields: `AccountNumber,ClientId,Pin`

## Transitions
- `on0Do` -> [GetBalance](opsteps/GetBalance.md)
- `onOtherDo` -> [ValidationFailed](opsteps/ValidationFailed.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- RequiredFields: `AccountNumber,ClientId,Pin`
- id: `ValidateRequest`
- implClass: `com.ibm.il.dse.operations.common.ValidateInputFields`
- on0Do: `GetBalance`
- onOtherDo: `ValidationFailed`
