# FraudCheck

---
entity_type: opStep
entity_id: FraudCheck
conversion_status: not_started
used_by_operations:
  - TransferFundsOp
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\Xml Definition\Channel\INTERNET\selfDefOper\TransferFunds.xml
source_hash: 71e86b8b16811414061e81e82a1634ea9ae2dad8c37da555c01db40a4c5c8ba5
---

## Implementation
- [com.ibm.il.dse.operations.internet.service.CallFraudDetection](classes/com/ibm/il/dse/operations/internet/service/CallFraudDetection.md)

## Parameters
- ServiceTimeout: `5000`

## Transitions
- `on0Do` -> [ExecuteTransfer](opsteps/ExecuteTransfer.md)
- `on2Do` -> [FraudSuspected](opsteps/FraudSuspected.md)
- `onOtherDo` -> [TechnicalError](opsteps/TechnicalError.md)
- `onTimeoutDo` -> [SkipFraudOnTimeout](opsteps/SkipFraudOnTimeout.md)

## Parser Notes
- Transition attributes are detected with the `on*Do` naming pattern. Verify this covers all transition names used in the source WSBCC codebase before relying on `Parameters` as transition-free.

## Raw Attributes
- ServiceTimeout: `5000`
- id: `FraudCheck`
- implClass: `com.ibm.il.dse.operations.internet.service.CallFraudDetection`
- on0Do: `ExecuteTransfer`
- on2Do: `FraudSuspected`
- onOtherDo: `TechnicalError`
- onTimeoutDo: `SkipFraudOnTimeout`
