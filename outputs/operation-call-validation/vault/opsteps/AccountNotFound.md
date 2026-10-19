# AccountNotFound

---
entity_type: opStep
entity_id: AccountNotFound
conversion_status: not_started
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Implementation
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Parameters
- ErrorCategory: `20`
- ErrorNumber: `4`

## Transitions
- `onOtherDo` -> unresolved `end`

## Return Body Switches
- When these return codes occur, the reply format body is switched to the named error format before the response is built.
- RC `0` -> switch reply body to `ErrorBody`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- ErrorCategory: `20`
- ErrorNumber: `4`
- id: `AccountNotFound`
- implClass: `com.ibm.il.dse.operations.common.MapErrorByValueAlways`
- on0Return: `ErrorBody`
- onOtherDo: `end`
