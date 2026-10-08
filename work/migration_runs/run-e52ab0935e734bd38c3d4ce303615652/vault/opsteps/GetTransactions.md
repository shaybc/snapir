# GetTransactions

---
entity_type: opStep
entity_id: GetTransactions
conversion_status: not_started
used_by_operations:
  - GetAccountDetailsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\GetAccountDetails.xml
source_hash: 3b0a5c48426c37795e96fa132e1ae902d2a7f7181f2e3d60a7754a1b644d83f7
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.GetAccountTransactionsSP](classes/com/ibm/il/dse/operations/internet/db/GetAccountTransactionsSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> unresolved `end`
- `on4Do` -> unresolved `end`
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `GetTransactions`
- implClass: `com.ibm.il.dse.operations.internet.db.GetAccountTransactionsSP`
- on0Do: `end`
- on4Do: `end`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
