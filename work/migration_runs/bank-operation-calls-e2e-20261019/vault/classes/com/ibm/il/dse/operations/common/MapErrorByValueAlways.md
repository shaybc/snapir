# com.ibm.il.dse.operations.common.MapErrorByValueAlways

---
entity_type: java_class
entity_id: com.ibm.il.dse.operations.common.MapErrorByValueAlways
conversion_status: not_started
shared: true
used_by_steps:
  - AccessDenied
  - AccountNotEligible
  - AccountNotFound
  - CoreBankingRejected
  - DailyLimitExceeded
  - DatabaseError
  - FraudSuspected
  - InsufficientFunds
  - NoAccountsFound
  - NoLinksFound
  - TechnicalError
  - TransferAlreadyProcessed
  - ValidationFailed
parent_class: com.ibm.dse.base.CCOperationStep
interfaces: []
source_file: C:\GitHub\shaybc\snapir\bank-demo\composer\Workspace\WSBCC_INTERNET\src\com\ibm\il\dse\operations\common\MapErrorByValueAlways.java
source_hash: 728019a09f6eaca78ce390b7464dc3b102fb895c35486189fc8b5fd6ff340aad
---

## Package
- `com.ibm.il.dse.operations.common`

## Behavior Type
- `error_mapper`

## IBM Dependency Warning
- This class imports IBM/WebSphere APIs and must be converted for non-WAS runtimes.
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inheritance
- extends: `com.ibm.dse.base.CCOperationStep`
- implements: none

## Return Codes
- Returns `0` (always (mapping always succeeds))

## Thrown Exceptions
- `Exception`

## Methods
- `setErrorCategory`
- `setErrorNumber`
- `execute`
- `resolveErrorDescription`

## Setter Methods
- `setErrorCategory`
- `setErrorNumber`

## Imports
- `com.ibm.dse.base.CCOperationStep`
- `com.ibm.dse.base.Context`

## Inferred External Dependencies
- IBM/WAS
