# ExecuteTransfer

---
entity_type: opStep
entity_id: ExecuteTransfer
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.ExecuteTransferSP](classes/com/ibm/il/dse/operations/internet/db/ExecuteTransferSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> unresolved `end`
- `on6Do` -> [CoreBankingRejected](opsteps/CoreBankingRejected.md)
- `on7Do` -> [TransferAlreadyProcessed](opsteps/TransferAlreadyProcessed.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `ExecuteTransfer`
- implClass: `com.ibm.il.dse.operations.internet.db.ExecuteTransferSP`
- on0Do: `end`
- on6Do: `CoreBankingRejected`
- on7Do: `TransferAlreadyProcessed`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
