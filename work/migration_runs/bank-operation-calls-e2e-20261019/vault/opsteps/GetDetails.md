# GetDetails

---
entity_type: opStep
entity_id: GetDetails
conversion_status: not_started
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.GetAccountDetailsSP](classes/com/ibm/il/dse/operations/internet/db/GetAccountDetailsSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> [GetTransactions](opsteps/GetTransactions.md)
- `on4Do` -> [AccountNotFound](opsteps/AccountNotFound.md)
- `on5Do` -> [AccessDenied](opsteps/AccessDenied.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetDetails`
- implClass: `com.ibm.il.dse.operations.internet.db.GetAccountDetailsSP`
- on0Do: `GetTransactions`
- on4Do: `AccountNotFound`
- on5Do: `AccessDenied`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
