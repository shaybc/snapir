# GetAccounts

---
entity_type: opStep
entity_id: GetAccounts
conversion_status: not_started
used_by_operations:
  - GetClientAccountsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetClientAccounts.xml
source_hash: c6d10b4ed4d931e4e2933f6afeb7d68804cec3db9f1e488ea24a74b332d31bb8
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.GetClientAccountsSP](classes/com/ibm/il/dse/operations/internet/db/GetClientAccountsSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> [NoAccountsFound](opsteps/NoAccountsFound.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetAccounts`
- implClass: `com.ibm.il.dse.operations.internet.db.GetClientAccountsSP`
- on0Do: `end`
- on4Do: `NoAccountsFound`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
