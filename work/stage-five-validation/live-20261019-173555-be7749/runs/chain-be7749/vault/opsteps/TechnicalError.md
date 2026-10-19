# TechnicalError

---
entity_type: opStep
entity_id: TechnicalError
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Implementation
- [com.ibm.il.dse.operations.common.MapErrorByValueAlways](classes/com/ibm/il/dse/operations/common/MapErrorByValueAlways.md)

## Parameters
- ErrorCategory: `99`
- ErrorNumber: `0`

## Transitions
- `onOtherDo` -> unresolved `end`

## Return Body Switches
- When these return codes occur, the reply format body is switched to the named error format before the response is built.
- RC `0` -> switch reply body to `ErrorBody`

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- ErrorCategory: `99`
- ErrorNumber: `0`
- id: `TechnicalError`
- implClass: `com.ibm.il.dse.operations.common.MapErrorByValueAlways`
- on0Return: `ErrorBody`
- onOtherDo: `end`
