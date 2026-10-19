# GetBalance

---
entity_type: opStep
entity_id: GetBalance
conversion_status: not_started
used_by_operations:
  - GetAccountBalanceOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetAccountBalance.xml
source_hash: 0fb403fd7c6dea2ff8390f4079959769b0e3c15a2c3538965bbb50b481dd4c2e
---

## Implementation
- [com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP](classes/com/ibm/il/dse/operations/ivr/db/GetAccountBalanceSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> [LogIvrCall](opsteps/LogIvrCall.md)
- `on4Do` -> [AccountNotFound](opsteps/AccountNotFound.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetBalance`
- implClass: `com.ibm.il.dse.operations.ivr.db.GetAccountBalanceSP`
- on0Do: `LogIvrCall`
- on4Do: `AccountNotFound`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
