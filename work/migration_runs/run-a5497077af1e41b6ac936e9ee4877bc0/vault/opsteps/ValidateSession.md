# ValidateSession

---
entity_type: opStep
entity_id: ValidateSession
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

## Implementation
- [com.ibm.il.dse.operations.common.ValidateInputFields](classes/com/ibm/il/dse/operations/common/ValidateInputFields.md)

## Parameters
- RequiredFields: `SessionToken,ClientId`

## Transitions
- `on0Do` -> [GetAccounts](opsteps/GetAccounts.md)
- `onOtherDo` -> [ValidationFailed](opsteps/ValidationFailed.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- RequiredFields: `SessionToken,ClientId`
- id: `ValidateSession`
- implClass: `com.ibm.il.dse.operations.common.ValidateInputFields`
- on0Do: `GetAccounts`
- onOtherDo: `ValidationFailed`
