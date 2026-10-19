# NoAccountsFound

---
entity_type: opStep
entity_id: NoAccountsFound
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

## Implementation
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Parameters
- ErrorCategory: `20`
- ErrorNumber: `1`

## Transitions
- `onOtherDo` -> unresolved `end`

## Return Body Switches
- When these return codes occur, the reply format body is switched to the named error format before the response is built.
- RC `0` -> switch reply body to `ErrorBody`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- ErrorCategory: `20`
- ErrorNumber: `1`
- id: `NoAccountsFound`
- implClass: `com.ibm.il.dse.operations.common.MapErrorByValueAlways`
- on0Return: `ErrorBody`
- onOtherDo: `end`
