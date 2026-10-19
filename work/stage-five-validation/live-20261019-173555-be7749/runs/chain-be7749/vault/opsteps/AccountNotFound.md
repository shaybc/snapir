# AccountNotFound

---
entity_type: opStep
entity_id: AccountNotFound
conversion_status: not_started
used_by_operations:
  - GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
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
