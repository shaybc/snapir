# GetAccounts

---
entity_type: opStep
entity_id: GetAccounts
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_IVR\src\Xml Definition\Channel\IVR\selfDefOper\GetClientAccounts.xml
source_hash: 9dcc938f33cbdec98354dbeb023d9574ed8f2df9476a13e128ee8f7b171d76dc
---

## Implementation
- [com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP](classes/com/ibm/il/dse/operations/ivr/db/GetClientAccountsIvrSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> [LogIvrCall](opsteps/LogIvrCall.md)
- `on4Do` -> [NoAccountsFound](opsteps/NoAccountsFound.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetAccounts`
- implClass: `com.ibm.il.dse.operations.ivr.db.GetClientAccountsIvrSP`
- on0Do: `LogIvrCall`
- on4Do: `NoAccountsFound`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
