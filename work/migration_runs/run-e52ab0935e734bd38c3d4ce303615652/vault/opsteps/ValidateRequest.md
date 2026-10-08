# ValidateRequest

---
entity_type: opStep
entity_id: ValidateRequest
conversion_status: not_started
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Implementation
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)

## Parameters
- RequiredFields: `AccountNumber,ClientId,SessionToken`

## Transitions
- `on0Do` -> [GetDetails](opsteps/GetDetails.md)
- `onOtherDo` -> [ValidationFailed](opsteps/ValidationFailed.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- RequiredFields: `AccountNumber,ClientId,SessionToken`
- id: `ValidateRequest`
- implClass: `com.ibm.il.dse.operations.common.ValidateInputFields`
- on0Do: `GetDetails`
- onOtherDo: `ValidationFailed`
