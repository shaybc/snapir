# CheckLimits

---
entity_type: opStep
entity_id: CheckLimits
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Implementation
- [com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP](classes/com/ibm/il/dse/operations/internet/db/ValidateTransferLimitsSP.md)

## Parameters
- None

## Transitions
- `on0Do` -> [FraudCheck](opsteps/FraudCheck.md)
- `on3Do` -> [DailyLimitExceeded](opsteps/DailyLimitExceeded.md)
- `on4Do` -> [InsufficientFunds](opsteps/InsufficientFunds.md)
- `on5Do` -> [AccountNotEligible](opsteps/AccountNotEligible.md)
- `on8Do` -> [DatabaseError](opsteps/DatabaseError.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- id: `CheckLimits`
- implClass: `com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP`
- on0Do: `FraudCheck`
- on3Do: `DailyLimitExceeded`
- on4Do: `InsufficientFunds`
- on5Do: `AccountNotEligible`
- on8Do: `DatabaseError`
- onOtherDo: `TechnicalError`
