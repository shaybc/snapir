# com.ibm.il.dse.operations.internet.service.CallFraudDetection

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.internet.service.CallFraudDetection
conversion_status: not_started
shared: false
used_by_steps:
  - FraudCheck
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\internet\service\CallFraudDetection.java
source_hash: 2347391cff69706616aa4c191746ed4e3aced3969987948e115b13c0f720c40c
---

## Package
- `com.ibm.il.dse.operations.internet.service`

## Behavior Type
- `unknown`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`
- `com.ibm.il.dse.cc.service.communication.http.HTTPService`

## Inheritance
- extends: `com.ibm.dse.base.CCOperationStep`
- implements: none

## Return Codes
- Returns `0` (100); fraud check passed (ALLOW decision))
- Returns `2` (fraud suspected (BLOCK decision)
- Returns `-99` (timeout (handled by onTimeoutDo routing))
- Returns `8` (service error)

## Thrown Exceptions
- `Exception`

## Methods
- `setServiceTimeout`
- `execute`
- `buildFraudRequest`
- `parseFraudScore`
- `parseFraudDecision`

## Setter Methods
- `setServiceTimeout`

## Imports
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`
- `com.ibm.il.dse.cc.service.communication.http.HTTPService`
- `java.math.BigDecimal`

## Inferred External Dependencies
- IBM/WAS
