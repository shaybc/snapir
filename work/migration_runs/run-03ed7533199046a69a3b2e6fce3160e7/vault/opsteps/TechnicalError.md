# TechnicalError

---
entity_type: opStep
entity_id: TechnicalError
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
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
